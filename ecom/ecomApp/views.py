from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import CustomUser, Product, ChatMessage, Category
from .forms import ProductForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
# AI imports
import os
import chromadb
import google.generativeai as genai
from chromadb import PersistentClient
from chromadb.errors import NotFoundError

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
# Initialise Gemini model once
GEMINI_MODEL = genai.GenerativeModel("gemini-1.5-flash")

# Initialize (persistent) Chroma client once per process
# Compute project root (two levels up from this file)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
CHROMA_PATH = os.path.join(ROOT_DIR, "chroma_db")
CHROMA_CLIENT = PersistentClient(path=CHROMA_PATH)
try:
    CHROMA_COLLECTION = CHROMA_CLIENT.get_collection(name="product_profiles")
except (ValueError, NotFoundError):
    CHROMA_COLLECTION = CHROMA_CLIENT.create_collection(name="product_profiles")

import json
from django.core.paginator import Paginator

def home(request):
    if request.user.is_authenticated:
        if getattr(request.user, 'is_vendor', False):
            return redirect('vendor_dashboard')
        if getattr(request.user, 'is_retailer', False):
            return redirect('retailer_dashboard')
    return render(request, 'home.html', {'title': 'Home'})

def register_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        role = request.POST['role']  # 'vendor' or 'retailer'
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
            return render(request, 'register.html')
        user = CustomUser.objects.create_user(username=username, email=email, password=password)
        if role == 'vendor':
            user.is_vendor = True
        elif role == 'retailer':
            user.is_retailer = True
        user.save()
        messages.success(request, 'Registration successful! Please log in.')
        return redirect('login')
    return render(request, 'register.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.is_vendor:
                return redirect('/vendor/dashboard/')
            elif user.is_retailer:
                return redirect('/retailer/dashboard/')
            else:
                return redirect('home')
        else:
            messages.error(request, 'Invalid credentials')
            return redirect('login')
    return render(request, 'login.html')

def is_vendor(user):
    return user.is_authenticated and getattr(user, 'is_vendor', False)

def is_retailer(user):
    return user.is_authenticated and getattr(user, 'is_retailer', False)

@login_required
@user_passes_test(is_retailer, login_url='/')

def browse_products(request):
    """Retailer browse all products with optional global search."""
    from django.db.models import Avg, Q

    search_query = request.GET.get('search', '').strip()

    products_qs = Product.objects.filter(available=True, quantity__gt=0)
    if search_query:
        products_qs = products_qs.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(category__name__icontains=search_query) |
            Q(vendor__username__icontains=search_query)
        )

    products_qs = products_qs.annotate(avg_rating=Avg('feedbacks__rating'))

    paginator = Paginator(products_qs, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'browse_products.html', {
        'page_obj': page_obj,
        'products': page_obj.object_list,
        'search_query': search_query,
    })

@login_required
@user_passes_test(is_retailer, login_url='/')
def product_detail(request, id):
    from django.shortcuts import get_object_or_404
    from .models import Feedback
    from django.db.models import Avg
    product = get_object_or_404(Product, id=id, available=True)
    feedbacks = product.feedbacks.select_related('retailer')
    avg_rating = feedbacks.aggregate(avg=Avg('rating'))['avg']
    return render(request, 'product_detail.html', {
        'product': product,
        'feedbacks': feedbacks,
        'avg_rating': avg_rating
    })

@login_required
@user_passes_test(is_retailer, login_url='/')
def cart(request):
    from .models import CartItem, Category
    from decimal import Decimal
    cart_items = CartItem.objects.select_related('product', 'product__category', 'cart').filter(cart__retailer=request.user, cart__status='active')
    ai_cart_items = [item for item in cart_items if item.auto_added]
    regular_cart_items = [item for item in cart_items if not item.auto_added]
    # Totals
    total = Decimal('0')
    ai_total = Decimal('0')
    regular_total = Decimal('0')
    category_breakdown = {}
    for item in cart_items:
        subtotal = item.product.price * item.quantity
        item.subtotal = subtotal  # Add subtotal to each item
        total += subtotal
        if item.auto_added:
            ai_total += subtotal
        else:
            regular_total += subtotal
        cat = item.product.category.name if item.product.category else 'Uncategorized'
        category_breakdown.setdefault(cat, Decimal('0'))
        category_breakdown[cat] += subtotal
    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'ai_cart_items': ai_cart_items,
        'regular_cart_items': regular_cart_items,
        'cart_total': total,
        'ai_total': ai_total,
        'regular_total': regular_total,
        'category_breakdown': category_breakdown
    })

@login_required
@user_passes_test(is_retailer, login_url='/')
def add_to_cart(request, product_id):
    from .models import Cart, CartItem, Product
    from django.shortcuts import get_object_or_404
    product = get_object_or_404(Product, id=product_id, available=True)
    # Get or create active cart for this retailer
    cart, _ = Cart.objects.get_or_create(retailer=request.user, status='active')
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1}
    )
    if not created:
        # Do not exceed available stock
        if cart_item.quantity + 1 > product.quantity:
            messages.warning(request, f"Only {product.quantity} of {product.name} available in stock.")
        else:
            cart_item.quantity += 1
            cart_item.save()
    return redirect('cart')

@login_required
@user_passes_test(is_retailer, login_url='/')
def remove_from_cart(request, item_id):
    from .models import Cart, CartItem
    cart = Cart.objects.filter(retailer=request.user, status='active').first()
    if not cart:
        return redirect('cart')
    cart_item = CartItem.objects.filter(id=item_id, cart=cart).first()
    if cart_item and request.method == 'POST':
        cart_item.delete()
    return redirect('cart')

@login_required
@user_passes_test(is_retailer, login_url='/')
def update_cart_quantity(request, item_id):
    from .models import Cart, CartItem
    cart = Cart.objects.filter(retailer=request.user, status='active').first()
    if not cart:
        return redirect('cart')
    cart_item = CartItem.objects.filter(id=item_id, cart=cart).first()
    if cart_item and request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 1))
            max_available = cart_item.product.quantity
            if quantity > max_available:
                messages.warning(request, f"Only {max_available} items available for {cart_item.product.name}.")
                quantity = max_available
            if quantity > 0:
                cart_item.quantity = quantity
                cart_item.save()
            else:
                cart_item.delete()
        except ValueError:
            pass
    return redirect('cart')

@login_required
@user_passes_test(is_retailer, login_url='/')
def checkout(request):
    from .models import Cart, CartItem, Order, OrderItem
    from django.db import transaction
    from decimal import Decimal
    
    # Get active cart for this retailer
    cart = Cart.objects.filter(retailer=request.user, status='active').first()
    if not cart:
        messages.error(request, 'No active cart found.')
        return redirect('cart')
    
    cart_items = CartItem.objects.filter(cart=cart)
    if request.method == 'POST':
        if not cart_items.exists():
            messages.error(request, 'Your cart is empty.')
            return redirect('cart')
            
        total = sum(item.product.price * item.quantity for item in cart_items)
        
        with transaction.atomic():
            # Re-validate stock before committing
            for item in cart_items:
                if item.quantity > item.product.quantity:
                    messages.error(request, f"Not enough stock for {item.product.name}. Available: {item.product.quantity}")
                    return redirect('cart')
            # Create order
            order = Order.objects.create(
                retailer=request.user,
                total_price=total,
                status='pending'
            )
            # Create order items and reduce stock
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    vendor=item.product.vendor,
                    quantity=item.quantity,
                    price_at_order_time=item.product.price,
                    added_by='AI' if item.auto_added else 'Manual'
                )
                # Decrease product stock
                item.product.quantity -= item.quantity
                item.product.save()
            # Clear cart and items
            cart_items.delete()
            cart.delete()
            
        messages.success(request, f'Order #{order.id} placed successfully!')
        return redirect('retailer_order_history')
    
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render(request, 'checkout.html', {'cart_items': cart_items, 'total': total})

@login_required
@user_passes_test(is_retailer, login_url='/')
def order_summary(request):
    from .models import Order
    order = Order.objects.filter(retailer=request.user).order_by('-created_at').first()
    return render(request, 'order_summary.html', {'order': order})

@login_required
@user_passes_test(is_retailer, login_url='/')
def retailer_dashboard(request):
    return render(request, 'retailer_dashboard.html')

@login_required
@user_passes_test(is_retailer, login_url='/')
def order_feedback(request, order_id):
    from .models import Order, Feedback, OrderItem
    order = Order.objects.filter(id=order_id, retailer=request.user).first()
    if not order or order.status != 'delivered':
        messages.warning(request, 'Feedback is available only after delivery.')
        return redirect('retailer_order_history')
    # one feedback per vendor per order
    items = OrderItem.objects.select_related('product').filter(order=order, product__available=True)
    if request.method == 'POST':
        for item in items:
            rating = int(request.POST.get(f'rating_{item.id}', '5'))
            comment = request.POST.get(f'comment_{item.id}', '')
            Feedback.objects.create(order=order, product=item.product, vendor=item.product.vendor,
                                    retailer=request.user, rating=rating, comment=comment)
        messages.success(request, 'Thank you for rating the products!')
        return redirect('retailer_order_history')
    return render(request, 'order_feedback.html', {'order': order, 'items': items})

def retailer_order_history(request):
    from .models import Order, OrderItem
    from decimal import Decimal
    
    # Get all orders for this retailer
    orders_qs = Order.objects.filter(retailer=request.user).order_by('-created_at')
    from django.core.paginator import Paginator
    paginator = Paginator(orders_qs, 5)
    page_number = request.GET.get('page')
    orders = paginator.get_page(page_number)
    
    # Group orders with their items
    orders_with_items = []
    for order in orders:
        order_items = OrderItem.objects.select_related('product', 'product__vendor').filter(order=order)
        
        # Calculate order total
        order_total = Decimal('0')
        for item in order_items:
            order_total += item.price_at_order_time * item.quantity
            
        orders_with_items.append({
            'order': order,
            'items': order_items,
            'total': order_total
        })
    
    return render(request, 'retailer_orders.html', {
        'orders_with_items': orders_with_items,
        'page_obj': orders
    })

# AI shopping assistant removed

# Vendor AI command functionality removed - AI assistant is only available for retailers

@login_required
@user_passes_test(is_vendor, login_url='/')
def vendor_overview(request):

    from django.db.models import Avg

    return render(request, 'vendor_home.html', {
        'products': products,
        'more_products': more_products,
        'avg_price': avg_price,
        'best_priced': best_priced,
    })

@login_required
@user_passes_test(is_vendor, login_url='/')
def vendor_orders(request):
    """List orders for vendor's products"""
    from .models import OrderItem, Order, Feedback
    order_items = OrderItem.objects.select_related('order', 'product').filter(product__vendor=request.user).order_by('-order__created_at')
    orders_dict = {}
    for item in order_items:
        oid = item.order.id
        if oid not in orders_dict:
            orders_dict[oid] = {
                'order': item.order,
                'retailer': item.order.retailer,
                'items': [],
                'feedbacks': [],
            }
        fb = Feedback.objects.filter(order=item.order, product=item.product).first()
        item.order_rating = fb.rating if fb else None
        orders_dict[oid]['items'].append(item)
        orders_dict[oid]['feedbacks'] = Feedback.objects.filter(order=item.order, vendor=request.user)
    orders_list = list(orders_dict.values())
    from django.core.paginator import Paginator
    paginator = Paginator(orders_list, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    status_choices = Order.STATUS_CHOICES
    return render(request, 'vendor_orders.html', {
        'page_obj': page_obj,
        'orders': page_obj.object_list,
        'status_choices': status_choices,
    })


@login_required
@user_passes_test(is_vendor, login_url='/')
def vendor_dashboard(request):
    """Vendor Dashboard - Analytics overview only"""
    from .models import Product
    from django.db.models import Avg
    total_products = Product.objects.filter(vendor=request.user).count()
    low_stock_products = Product.objects.filter(vendor=request.user, quantity__lt=10).count()
    avg_price = Product.objects.filter(vendor=request.user).aggregate(avg=Avg('price'))['avg'] or 0
    best_priced = Product.objects.filter(vendor=request.user).order_by('price').first()

    # --- Sales & Performance Metrics (last 30 days) ---
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Sum, F, DecimalField, Avg, Count
    from .models import OrderItem, Order, Feedback
    now = timezone.now()
    last_30 = now - timedelta(days=30)
    last_7 = now - timedelta(days=7)

    order_items_30 = OrderItem.objects.select_related('order').filter(
        product__vendor=request.user,
        order__created_at__gte=last_30
    )
    sales_30 = order_items_30.aggregate(total=Sum(F('quantity') * F('price_at_order_time'), output_field=DecimalField()))['total'] or 0
    units_30 = order_items_30.aggregate(total=Sum('quantity'))['total'] or 0

    orders_30 = Order.objects.filter(items__product__vendor=request.user, created_at__gte=last_30).distinct()
    order_count_30 = orders_30.count()
    aov_30 = (sales_30 / order_count_30) if order_count_30 else 0

    # Order pipeline snapshot
    pending_orders = Order.objects.filter(items__product__vendor=request.user, status='pending').distinct().count()

    # Feedback metrics
    avg_rating_overall = Feedback.objects.filter(vendor=request.user).aggregate(avg=Avg('rating'))['avg'] or 0

    # Top 5 products by units sold (last 30 days)
    top_products = list(order_items_30.values('product__name').annotate(units=Sum('quantity')).order_by('-units')[:5])
    return render(request, 'vendor_dashboard.html', {
        # Core inventory stats
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'avg_price': avg_price,
        'best_priced': best_priced,
        # Sales KPIs
        'sales_30': sales_30,
        'units_30': units_30,
        'aov_30': aov_30,
        # Operational
        'pending_orders': pending_orders,
        # Customer satisfaction
        'avg_rating_overall': avg_rating_overall,
        # Top products list
        'top_products': top_products
    })

@login_required
@user_passes_test(is_vendor, login_url='/')
def update_order_status(request, order_id):
    from .models import Order, OrderItem
    order = Order.objects.get(id=order_id)
    # If order already delivered, do not allow further modifications
    if order.status == 'delivered':
        messages.info(request, 'Order already delivered. Status can no longer be changed.')
        return redirect('vendor_dashboard')
    # Check if this vendor has at least one product in this order
    has_vendor_product = OrderItem.objects.filter(order=order, product__vendor=request.user).exists()
    if not has_vendor_product:
        return redirect('vendor_dashboard')
    if request.method == 'POST':
        status = request.POST.get('status')
        if status == 'delivered':
            # Mark ONLY this vendor's items as delivered
            OrderItem.objects.filter(order=order, product__vendor=request.user).update(delivered=True)
            # If ALL items in the order are delivered, close the order
            if not OrderItem.objects.filter(order=order, delivered=False).exists():
                order.status = 'delivered'
                order.save()
            messages.success(request, "Delivery status updated.")
        else:
            # allow vendor to mark his items processing/dispatched etc.
            order.status = status
            order.save()
    return redirect('vendor_dashboard')

@login_required
@user_passes_test(is_vendor, login_url='/')
def vendor_products(request):
    from .models import Product, Category
    from django.db.models import Avg, Min, Max
    # Fetch all categories for dropdown
    categories = Category.objects.all()
    # Get filter params
    price_min = request.GET.get('price_min')
    price_max = request.GET.get('price_max')
    category_id = request.GET.get('category')
    stock = request.GET.get('stock')  # 'in' or 'out'
    sort = request.GET.get('sort')  # 'price', 'date', 'quantity'
    products = Product.objects.filter(vendor=request.user).annotate(avg_rating=Avg('feedbacks__rating'))
    # Filter by price
    if price_min:
        products = products.filter(price__gte=price_min)
    if price_max:
        products = products.filter(price__lte=price_max)
    # Filter by category
    if category_id and category_id != 'all':
        products = products.filter(category_id=category_id)
    # Filter by stock
    if stock == 'in':
        products = products.filter(quantity__gt=0)
    elif stock == 'out':
        products = products.filter(quantity=0)
    # Sorting
    if sort == 'price':
        products = products.order_by('price')
    elif sort == 'date':
        products = products.order_by('-created_at')
    elif sort == 'quantity':
        products = products.order_by('quantity')
    # Analytics
    total_products = products.count()
    low_stock_products = products.filter(quantity__lt=10).count()
    avg_price = products.aggregate(avg=Avg('price'))['avg'] or 0
    best_priced = products.order_by('price').first()
    # For price slider range
    min_price = Product.objects.filter(vendor=request.user).aggregate(min=Min('price'))['min'] or 0
    max_price = Product.objects.filter(vendor=request.user).aggregate(max=Max('price'))['max'] or 0
    return render(request, 'vendor_products.html', {
        'products': products,
        'categories': categories,
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'avg_price': avg_price,
        'best_priced': best_priced,
        'min_price': min_price,
        'max_price': max_price,
        'selected_category': category_id or 'all',
        'selected_stock': stock or '',
        'selected_sort': sort or '',
        'selected_price_min': price_min or min_price,
        'selected_price_max': price_max or max_price,
    })

@login_required
@user_passes_test(is_vendor, login_url='/')
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.vendor = request.user
            product.save()
            return redirect('vendor_products')
    else:
        form = ProductForm()
    return render(request, 'product_form.html', {'form': form, 'title': 'Add Product'})

@login_required
@user_passes_test(is_vendor, login_url='/')
def edit_product(request, id):
    product = Product.objects.get(id=id, vendor=request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            return redirect('vendor_products')
    else:
        form = ProductForm(instance=product)
    return render(request, 'product_form.html', {'form': form, 'title': 'Edit Product'})

@login_required
@user_passes_test(is_vendor, login_url='/')
def delete_product(request, id):
    product = Product.objects.get(id=id, vendor=request.user)
    if request.method == 'POST':
        product.delete()
        return redirect('vendor_products')
    return render(request, 'confirm_delete.html', {'product': product})

def retailer_dashboard(request):
    if not request.user.is_authenticated or not getattr(request.user, 'is_retailer', False):
        return redirect('login')
    return render(request, 'retailer_dashboard.html', {'user': request.user})

def logout_view(request):
    logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('login')

# Vendor Browsing Views for Retailers
@login_required
@user_passes_test(lambda u: getattr(u, 'is_retailer', False), login_url='/')
def vendor_list(request):
    """Display list of all vendors for retailers to browse"""
    vendors_qs = CustomUser.objects.filter(is_vendor=True)
    from django.core.paginator import Paginator
    paginator = Paginator(vendors_qs, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # annotate product_count lazily
    vendors = list(page_obj.object_list)
    for vendor in vendors:
        vendor.product_count = Product.objects.filter(vendor=vendor, available=True).count()
    return render(request, 'vendor_list.html', {
        'vendors': vendors,
        'page_obj': page_obj,
        'user': request.user
    })

@login_required
@user_passes_test(lambda u: getattr(u, 'is_retailer', False), login_url='/')
def vendor_detail(request, vendor_id):
    """Display specific vendor's products for retailers"""
    from django.shortcuts import get_object_or_404
    
    vendor = get_object_or_404(CustomUser, id=vendor_id, is_vendor=True)
    products = Product.objects.filter(vendor=vendor, available=True).select_related('category')
    
        # Search & filter functionality
    from django.db.models import Q
    search_query = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', '').strip()

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )
        # Inform user if no matching item found for this vendor
        if not products.exists():
            messages.info(request, f'"{search_query}" is not available from {vendor.username}.')
    
    if category_filter:
        products = products.filter(category__name=category_filter)
    
    # Get categories for filter dropdown
    categories = Category.objects.filter(
        products__vendor=vendor, 
        products__available=True
    ).distinct()
    
    return render(request, 'vendor_detail.html', {
        'vendor': vendor,
        'products': products,
        'categories': categories,
        'search_query': search_query,
        'category_filter': category_filter,
        'user': request.user
    })

# ---------------------------
# RAG – Ask AI View
# ---------------------------
from django.views.decorators.http import require_http_methods

def generate_rag_answer(query: str) -> str:
    """Generate RAG answer using Chroma + Gemini, returns text string"""
    if CHROMA_COLLECTION is None:
        return "Knowledge base not initialised. Please embed data first."
    # embedding
    embed_resp = genai.embed_content(model="models/embedding-001", content=query, task_type="retrieval_query")
    query_embedding = embed_resp["embedding"]
    results = CHROMA_COLLECTION.query(query_embeddings=[query_embedding], n_results=3)
    documents = results["documents"][0] if results["documents"] else []
    context = "\n".join(documents)
    prompt = (
        "You are an e-commerce assistant. "
        "Using the following context, answer the user's question as helpfully as possible.\n\n" +
        f"Context:\n{context}\n\nUser question: {query}"
    )
    chat_resp = GEMINI_MODEL.generate_content(prompt)
    return chat_resp.text.strip()


@login_required
@require_http_methods(["GET"])
def chat_ui(request):
    """Render the chat interface page"""
    return render(request, "chat.html")

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def chat_send(request):
    """AJAX endpoint to receive user message and return AI reply"""
    user_msg = request.POST.get("message", "").strip()
    if not user_msg:
        return JsonResponse({"error": "empty message"}, status=400)
    answer = generate_rag_answer(user_msg)
    return JsonResponse({"reply": answer})


def ask_ai(request):
    """Retrieve relevant product context via Chroma + answer with OpenAI chat."""
    if request.method == "POST":
        query = request.POST.get("query", "").strip()
        if not query:
            messages.error(request, "Please enter a question.")
            return redirect("ask_ai")

        if CHROMA_COLLECTION is None:
            messages.error(request, "Knowledge base not initialised. Please embed data first.")
            return redirect("ask_ai")

        answer = generate_rag_answer(query)

        return render(request, "rag_response.html", {"query": query, "response": answer})

    return render(request, "ask.html")
