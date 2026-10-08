from django.db import models
from django.contrib.auth.models import User


class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    stock = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def is_available(self):
        """Returns True if the product has at least one unit in stock."""
        return self.stock > 0


class Order(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Processing", "Processing"),
        ("Shipped", "Shipped"),
        ("Delivered", "Delivered"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    address = models.TextField()
    phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    # Tracks when an admin last changed the order status.
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.id} — {self.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    # PROTECT prevents accidental product deletion from breaking order history.
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    # Snapshot of the price at the time of purchase; decoupled from Product.price.
    price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        """Server-side computed line total. Accessible in templates without ()."""
        return self.price * self.quantity

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"
