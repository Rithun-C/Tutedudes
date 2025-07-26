from django.urls import path
from . import views

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('vendor/orders/<int:order_id>/update_status/', views.update_order_status, name='update_order_status'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('vendor/overview/', views.vendor_overview, name='vendor_overview'),
    path('vendor/dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
    path('vendor/orders/', views.vendor_orders, name='vendor_orders'),
    path('retailer/dashboard/', views.retailer_dashboard, name='retailer_dashboard'),
    # Vendor product management
    path('vendor/products/', views.vendor_products, name='vendor_products'),
    path('vendor/products/add/', views.add_product, name='add_product'),
    path('vendor/products/<int:id>/edit/', views.edit_product, name='edit_product'),
    path('vendor/products/<int:id>/delete/', views.delete_product, name='delete_product'),
    # Retailer product browsing and cart
    path('retailer/products/', views.browse_products, name='browse_products'),
    path('retailer/products/<int:id>/', views.product_detail, name='product_detail'),
    path('retailer/cart/', views.cart, name='cart'),
    path('retailer/cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('retailer/cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('retailer/cart/update/<int:item_id>/', views.update_cart_quantity, name='update_cart_quantity'),
    path('retailer/checkout/', views.checkout, name='checkout'),
    path('retailer/order/summary/', views.order_summary, name='order_summary'),
    path('retailer/order/<int:order_id>/feedback/', views.order_feedback, name='order_feedback'),
    path('retailer/orders/', views.retailer_order_history, name='retailer_order_history'),
    # RAG AI query
    path('ai/ask/', views.ask_ai, name='ask_ai'),

    # Vendor browsing for retailers
    path('retailer/vendors/', views.vendor_list, name='vendor_list'),
    path('retailer/vendors/<int:vendor_id>/', views.vendor_detail, name='vendor_detail'),
]