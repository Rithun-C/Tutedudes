from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Product, CartItem, Order, OrderItem

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_vendor', 'is_retailer', 'is_staff')
    list_filter = ('is_vendor', 'is_retailer', 'is_staff', 'is_superuser')

    fieldsets = UserAdmin.fieldsets + (
        ('Role Information', {'fields': ('is_vendor', 'is_retailer')}),
    )

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'price', 'quantity', 'available', 'created_at')
    list_filter = ('vendor', 'available', 'created_at')
    search_fields = ('name', 'vendor__username')

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('product', 'cart', 'get_retailer', 'quantity', 'auto_added', 'added_at')
    list_filter = ('cart', 'auto_added', 'added_at')
    search_fields = ('cart__retailer__username', 'product__name')

    def get_retailer(self, obj):
        return obj.cart.retailer
    get_retailer.short_description = 'Retailer'

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'retailer', 'total_price', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('retailer__username',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'vendor', 'quantity', 'price_at_order_time', 'added_by')
    list_filter = ('vendor', 'added_by', 'order__status')
    search_fields = ('product__name', 'vendor__username', 'order__retailer__username')
