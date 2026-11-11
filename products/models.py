
from django.db import models

class Category(models.Model):
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='category_images/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} -> {self.name}"
        return self.name


class Product(models.Model):
    DISCOUNT_TYPE_CHOICES = (
        ('NONE', 'None'),
        ('FLAT', 'Flat'),
        ('PERCENTAGE', 'Percentage'),
    )

    APPROVAL_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    shop = models.ForeignKey('vendors.ShopProfile', on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    size = models.CharField(max_length=50, blank=True, null=True, help_text="Size of the product (e.g., M, L, XL, 42, 44)")
    
    stock_quantity = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=5, help_text="Threshold below which Low Stock Alert is triggered")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    moq = models.IntegerField("Minimum Order Quantity (MOQ)", default=1, help_text="Minimum amount a user must purchase")
    
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='NONE')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_start_date = models.DateTimeField(null=True, blank=True)
    discount_end_date = models.DateTimeField(null=True, blank=True)
    
    woner_commission = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Owner commission percentage (%)")
    
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='PENDING')
    rejection_reason = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [
            ("can_post_product", "Can post products"),
            ("can_auto_approve_product", "Can post product with direct auto-approval"),
            ("can_set_discount", "Can set product discounts"),
        ]

    def __str__(self):
        return self.title

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_images/')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.product.title} (Primary: {self.is_primary})"
