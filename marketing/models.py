from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ActiveWindowQuerySet(models.QuerySet):
    def live(self):
        """Active records whose optional start / end window includes now."""
        now = timezone.now()
        return self.filter(is_active=True).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gte=now),
        )


class Banner(models.Model):
    """Home page slider banner, managed from the admin dashboard."""
    title = models.CharField(max_length=255, blank=True)
    subtitle = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to='banners/', help_text='Recommended 1600×500 px')
    mobile_image = models.ImageField(upload_to='banners/', blank=True, null=True, help_text='Optional 800×600 px image for phones')
    link_url = models.CharField(max_length=500, blank=True, help_text='Where the banner goes when clicked, e.g. /products?category=5')
    button_text = models.CharField(max_length=60, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(blank=True, null=True)
    ends_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveWindowQuerySet.as_manager()

    class Meta:
        ordering = ['position', '-created_at']

    def __str__(self):
        return self.title or f'Banner #{self.pk}'


class LandingPage(models.Model):
    """A campaign page with a hand-picked set of products that can be ordered in one go."""
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True)
    headline = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    banner_image = models.ImageField(upload_to='landing/', blank=True, null=True)
    theme_color = models.CharField(max_length=7, default='#cc0066')
    cta_text = models.CharField(max_length=60, default='Order now')
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(blank=True, null=True)
    ends_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='landing_pages')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveWindowQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class LandingPageItem(models.Model):
    landing_page = models.ForeignKey(LandingPage, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='landing_items')
    position = models.PositiveIntegerField(default=0)
    is_preselected = models.BooleanField(default=False, help_text='Ticked by default on the order form')

    class Meta:
        ordering = ['position', 'id']
        unique_together = ('landing_page', 'product')

    def __str__(self):
        return f'{self.landing_page} → {self.product}'


class Coupon(models.Model):
    DISCOUNT_TYPES = (
        ('PERCENTAGE', 'Percentage'),
        ('FLAT', 'Flat amount'),
    )
    code = models.CharField(max_length=40, unique=True)
    description = models.CharField(max_length=255, blank=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES, default='PERCENTAGE')
    value = models.DecimalField(max_digits=10, decimal_places=2)
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text='Cap for percentage coupons')
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    usage_limit = models.PositiveIntegerField(blank=True, null=True, help_text='Total number of orders that can use this code')
    times_used = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(blank=True, null=True)
    ends_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ActiveWindowQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        self.code = (self.code or '').strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code

    def evaluate(self, subtotal):
        """Return (discount, error). `error` is None when the coupon applies to `subtotal`."""
        subtotal = Decimal(str(subtotal or 0))
        now = timezone.now()
        if not self.is_active or (self.starts_at and self.starts_at > now) or (self.ends_at and self.ends_at < now):
            return Decimal('0.00'), 'This coupon is not active.'
        if self.usage_limit is not None and self.times_used >= self.usage_limit:
            return Decimal('0.00'), 'This coupon has reached its usage limit.'
        if subtotal < self.min_order_amount:
            return Decimal('0.00'), f'Add items worth ৳{self.min_order_amount - subtotal:.0f} more to use this coupon.'
        if self.discount_type == 'PERCENTAGE':
            discount = (subtotal * self.value / Decimal('100')).quantize(Decimal('0.01'))
            if self.max_discount is not None:
                discount = min(discount, self.max_discount)
        else:
            discount = self.value
        return min(discount, subtotal), None


class SiteSettings(models.Model):
    """Single row of storefront contact details (floating WhatsApp button, hotline, footer)."""
    whatsapp_number = models.CharField(max_length=20, blank=True, help_text='Digits with country code, e.g. 8801712345678')
    whatsapp_message = models.CharField(max_length=255, blank=True, default='Hello! I would like to know about a book.')
    whatsapp_enabled = models.BooleanField(default=True)
    hotline = models.CharField(max_length=20, blank=True)
    support_email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    facebook_url = models.URLField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site settings'
        verbose_name_plural = 'Site settings'

    def __str__(self):
        return 'Site settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def whatsapp_url(self):
        if not (self.whatsapp_enabled and self.whatsapp_number):
            return None
        url = f'https://wa.me/{self.whatsapp_number}'
        return f'{url}?text={quote(self.whatsapp_message)}' if self.whatsapp_message else url
