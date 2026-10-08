from django.contrib import admin
from .models import Product, Order, OrderItem


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class OrderItemInline(admin.TabularInline):
    """Show line items directly on the Order change page."""
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "price", "subtotal")
    fields = ("product", "quantity", "price", "subtotal")

    # subtotal is a @property — expose it as a read-only column.
    def subtotal(self, obj):
        return obj.subtotal
    subtotal.short_description = "Subtotal"


# ---------------------------------------------------------------------------
# ModelAdmins
# ---------------------------------------------------------------------------

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "stock", "is_available", "created_at")
    list_editable = ("stock",)           # Edit stock directly from list view.
    list_filter = ("created_at",)
    search_fields = ("name", "description")
    readonly_fields = ("created_at",)

    @admin.display(boolean=True, description="In Stock")
    def is_available(self, obj):
        return obj.is_available


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "total_amount", "status", "created_at", "updated_at")
    list_editable = ("status",)           # Change status without opening each order.
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "phone", "address")
    readonly_fields = ("user", "total_amount", "created_at", "updated_at")
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "quantity", "price", "subtotal")
    readonly_fields = ("subtotal",)
    search_fields = ("order__id", "product__name")

    @admin.display(description="Subtotal")
    def subtotal(self, obj):
        return obj.subtotal
