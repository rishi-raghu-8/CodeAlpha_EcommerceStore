from django.core.management.base import BaseCommand
from store.models import Product

class Command(BaseCommand):
    help = "Create sample products"

    def handle(self, *args, **kwargs):
        products = [
            ("Wireless Headphones", "Comfortable wireless headphones with clear sound.", 2499, 15),
            ("Smart Watch", "Fitness tracking, notifications and modern design.", 3999, 10),
            ("Running Shoes", "Lightweight shoes for daily running and walking.", 1899, 20),
            ("Laptop Backpack", "Water-resistant backpack with laptop compartment.", 1299, 25),
            ("Mechanical Keyboard", "Compact keyboard with tactile switches.", 2999, 12),
            ("Bluetooth Speaker", "Portable speaker with powerful audio.", 1599, 18),
        ]
        for name, desc, price, stock in products:
            Product.objects.get_or_create(
                name=name,
                defaults={"description": desc, "price": price, "stock": stock}
            )
        self.stdout.write(self.style.SUCCESS("Sample products created."))
