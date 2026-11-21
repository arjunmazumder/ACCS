
from django.db import models

class Category(models.Model):
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='category_images/', blank=True, null=True)
    position = models.PositiveIntegerField(default=0, help_text="Display order (lower first), e.g. Class 1 before Class 2")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['position', 'name']

    MAX_DEPTH = 3  # category -> sub-category -> sub-sub-category

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} -> {self.name}"
        return self.name

    @property
    def ancestors(self):
        """Parent chain from the top-level category down to the direct parent."""
        chain, node, seen = [], self.parent, set()
        while node is not None and node.pk not in seen:
            seen.add(node.pk)
            chain.append(node)
            node = node.parent
        return chain[::-1]

    @property
    def depth(self):
        """1 for a top-level category, 2 for a sub-category, 3 for a sub-sub-category."""
        return len(self.ancestors) + 1

    @staticmethod
    def family_ids(ids):
        """The given category ids plus every descendant, at any depth."""
        family = {int(i) for i in ids}
        frontier = set(family)
        while frontier:
            children = set(Category.objects.filter(parent_id__in=frontier).values_list('id', flat=True)) - family
            family |= children
            frontier = children
        return family


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
    author = models.CharField(max_length=255, blank=True, null=True, help_text="Book author / writer")
    publisher = models.CharField(max_length=255, blank=True, null=True, help_text="Book publisher (prokashoni)")
    description = models.TextField(blank=True, null=True)
    preview_pdf = models.FileField(
        upload_to='product_previews/', blank=True, null=True,
        help_text='A few sample pages (PDF) that shoppers can read on the product page. Visible to everyone.',
    )
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

    # Denormalised from ProductReview for fast listing
    rating_avg = models.FloatField(default=0.0)
    rating_count = models.PositiveIntegerField(default=0)
    
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


class WishlistItem(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-created_at']


class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='product_reviews')
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')
        ordering = ['-created_at']

    def _refresh_product_rating(self):
        from django.db.models import Avg, Count
        stats = ProductReview.objects.filter(product_id=self.product_id).aggregate(avg=Avg('rating'), count=Count('id'))
        Product.objects.filter(id=self.product_id).update(rating_avg=round(stats['avg'] or 0, 2), rating_count=stats['count'])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._refresh_product_rating()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        self._refresh_product_rating()
        return result
