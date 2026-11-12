from django.contrib import admin

from .models import Banner, Coupon, LandingPage, LandingPageItem


class LandingPageItemInline(admin.TabularInline):
    model = LandingPageItem
    extra = 0
    raw_id_fields = ('product',)


@admin.register(LandingPage)
class LandingPageAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_active', 'created_at')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [LandingPageItemInline]


admin.site.register(Banner)
admin.site.register(Coupon)
