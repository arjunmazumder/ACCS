from django.contrib import admin
from .models import Category, Product, ProductImage

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'parent', 'created_at')
    list_filter = ('parent',)
    search_fields = ('name', 'description')


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'shop', 'price', 'woner_commission', 'approval_status', 'is_active', 'created_at')
    list_filter = ('approval_status', 'is_active')
    search_fields = ('title', 'shop__shop_name')
    inlines = [ProductImageInline]
