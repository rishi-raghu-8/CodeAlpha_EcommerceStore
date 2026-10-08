"""
store/views.py
==============
Production-ready views for the ShopEasy e-commerce store.

Key hardening applied over the original code
---------------------------------------------
* Race-condition fix: select_for_update() locks product rows inside
  transaction.atomic() so concurrent checkouts cannot over-sell.
* Double-validation: stock is re-validated *after* acquiring the DB lock,
  guaranteeing correctness even under high concurrency.
* Server-side totals: unit prices are read from the DB inside the locked
  transaction — client-supplied prices are never trusted.
* Cart session persistence: cart data is captured before login() cycles
  the session key and is restored immediately after, so a guest's cart
  survives both registration and login.
* Full messages coverage: every user action produces a contextual
  success / warning / error message.
"""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CheckoutForm, RegisterForm
from .models import Order, OrderItem, Product


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_cart(request) -> dict:
    """Return the cart dict from the session (product_id str → quantity int)."""
    return request.session.get("cart", {})


def _save_cart(request, cart_data: dict) -> None:
    """Persist the cart dict to the session and mark as modified."""
    request.session["cart"] = cart_data
    request.session.modified = True


# ---------------------------------------------------------------------------
# Public views
# ---------------------------------------------------------------------------

def home(request):
    products = Product.objects.all()
    q = request.GET.get("q", "").strip()
    if q:
        products = products.filter(name__icontains=q)
    return render(request, "store/home.html", {"products": products, "q": q})


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, "store/product_detail.html", {"product": product})


# ---------------------------------------------------------------------------
# Cart views
# ---------------------------------------------------------------------------

def cart(request):
    """
    Display cart contents. Automatically warns the user if any item's
    carted quantity now exceeds available stock (e.g. stock was reduced
    after the item was added).
    """
    raw = get_cart(request)
    items, total = [], Decimal("0.00")

    for product_id, qty in list(raw.items()):
        product = Product.objects.filter(pk=product_id).first()
        if not product:
            # Product was deleted — silently remove from cart.
            raw.pop(product_id, None)
            continue

        qty = int(qty)

        # Warn if carted quantity exceeds current stock.
        if qty > product.stock:
            messages.warning(
                request,
                f"Only {product.stock} unit(s) of '{product.name}' are available. "
                f"Your cart quantity has been adjusted.",
            )
            qty = product.stock
            if qty == 0:
                raw.pop(product_id, None)
                continue
            raw[product_id] = qty

        subtotal = product.price * qty
        total += subtotal
        items.append({"product": product, "quantity": qty, "subtotal": subtotal})

    _save_cart(request, raw)
    return render(request, "store/cart.html", {"items": items, "total": total})


def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if not product.is_available:
        messages.error(request, f"'{product.name}' is currently out of stock.")
        return redirect("product_detail", pk=pk)

    cart_data = get_cart(request)
    key = str(pk)
    current = int(cart_data.get(key, 0))

    if current < product.stock:
        cart_data[key] = current + 1
        _save_cart(request, cart_data)
        messages.success(request, f"'{product.name}' added to your cart.")
    else:
        messages.warning(
            request,
            f"You already have the maximum available stock of '{product.name}' in your cart.",
        )

    return redirect(request.META.get("HTTP_REFERER", "home"))


def update_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    try:
        qty = max(0, int(request.POST.get("quantity", 1)))
    except (ValueError, TypeError):
        messages.error(request, "Invalid quantity.")
        return redirect("cart")

    # Silently cap at available stock to prevent over-ordering.
    if qty > product.stock:
        qty = product.stock
        messages.warning(
            request,
            f"Quantity for '{product.name}' has been capped at available stock ({product.stock}).",
        )

    cart_data = get_cart(request)
    if qty:
        cart_data[str(pk)] = qty
        messages.success(request, f"'{product.name}' quantity updated to {qty}.")
    else:
        cart_data.pop(str(pk), None)
        messages.success(request, f"'{product.name}' removed from your cart.")

    _save_cart(request, cart_data)
    return redirect("cart")


def remove_from_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart_data = get_cart(request)
    cart_data.pop(str(pk), None)
    _save_cart(request, cart_data)
    messages.success(request, f"'{product.name}' has been removed from your cart.")
    return redirect("cart")


# ---------------------------------------------------------------------------
# Auth views
# ---------------------------------------------------------------------------

def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            # ----------------------------------------------------------------
            # Cart persistence across session cycle
            # Django's login() calls cycle_key() which issues a new session
            # key. The session *data* is preserved by Django's implementation,
            # but we explicitly snapshot and restore the cart to be safe and
            # to handle any edge cases where the backend might not copy data.
            # ----------------------------------------------------------------
            cart_before = get_cart(request)

            user = form.save()
            login(request, user)

            # Restore cart in the new session.
            if cart_before:
                _save_cart(request, cart_before)

            messages.success(
                request,
                f"Welcome, {user.username}! Your account has been created successfully.",
            )
            return redirect("home")
    else:
        form = RegisterForm()

    return render(request, "store/register.html", {"form": form})


# ---------------------------------------------------------------------------
# Protected views (require login)
# ---------------------------------------------------------------------------

@login_required
def checkout(request):
    raw = get_cart(request)

    if not raw:
        messages.warning(request, "Your cart is empty. Add some products before checking out.")
        return redirect("cart")

    # ------------------------------------------------------------------
    # Pre-flight stock check (outside transaction, for early user feedback).
    # We do a second, locked check inside the transaction to handle races.
    # ------------------------------------------------------------------
    preflight_items = []
    for pid, qty in raw.items():
        product = get_object_or_404(Product, pk=pid)
        qty = int(qty)
        if qty > product.stock:
            if product.stock == 0:
                messages.error(
                    request,
                    f"Sorry, '{product.name}' is no longer in stock. "
                    f"It has been removed from your cart.",
                )
                raw.pop(pid, None)
            else:
                messages.error(
                    request,
                    f"Only {product.stock} unit(s) of '{product.name}' are available "
                    f"(you requested {qty}). Please update your cart.",
                )
            _save_cart(request, raw)
            return redirect("cart")
        preflight_items.append((product, qty))

    # Compute display total for the GET form (server-side, no client trust).
    display_total = sum(p.price * q for p, q in preflight_items)

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order = _place_order(request, form, raw)
            except ValueError as exc:
                # _place_order raises ValueError with a user-friendly message
                # when a race condition is detected inside the locked transaction.
                messages.error(request, str(exc))
                return redirect("cart")

            request.session["cart"] = {}
            request.session.modified = True
            messages.success(
                request,
                f"🎉 Order #{order.pk} placed successfully! "
                f"We'll start processing it shortly.",
            )
            return redirect("order_detail", pk=order.pk)
    else:
        form = CheckoutForm()

    return render(
        request,
        "store/checkout.html",
        {"form": form, "products": preflight_items, "total": display_total},
    )


def _place_order(request, form, raw: dict) -> Order:
    """
    Create the Order and OrderItems inside a single atomic transaction.

    Uses SELECT FOR UPDATE to lock the product rows, then re-validates stock
    so that concurrent checkouts cannot over-sell inventory.

    Raises ValueError with a user-friendly message if stock is insufficient.
    """
    product_ids = [int(pid) for pid in raw.keys()]

    with transaction.atomic():
        # Lock all involved product rows for the duration of this transaction.
        locked_products = {
            p.pk: p
            for p in Product.objects.select_for_update().filter(pk__in=product_ids)
        }

        # Build order items, validating stock with locked data.
        order_items = []
        server_total = Decimal("0.00")

        for pid, qty in raw.items():
            product = locked_products.get(int(pid))
            qty = int(qty)

            if product is None:
                raise ValueError(
                    f"A product in your cart (ID {pid}) no longer exists. "
                    f"Please refresh your cart."
                )

            if qty > product.stock:
                raise ValueError(
                    f"Sorry, only {product.stock} unit(s) of '{product.name}' are "
                    f"available now (another customer may have just purchased some). "
                    f"Please update your cart and try again."
                )

            # Server-side total — never trust client-submitted prices.
            line_total = product.price * qty
            server_total += line_total
            order_items.append((product, qty, product.price))

        # Persist the order with the server-computed total.
        order = form.save(commit=False)
        order.user = request.user
        order.total_amount = server_total
        order.save()

        # Persist items and decrement stock atomically.
        for product, qty, price_snapshot in order_items:
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=qty,
                price=price_snapshot,   # Price locked at purchase time.
            )
            product.stock -= qty
            product.save(update_fields=["stock"])

    return order


@login_required
def orders(request):
    user_orders = request.user.orders.prefetch_related("items__product").all()
    return render(request, "store/orders.html", {"orders": user_orders})


@login_required
def order_detail(request, pk):
    # user=request.user ensures users can only view their own orders.
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, "store/order_detail.html", {"order": order})
