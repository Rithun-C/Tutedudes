#!/usr/bin/env python
"""
Comprehensive Test Script for Intelligent Retailer Assistant
Tests all major functionalities and natural language processing capabilities
"""

import os
import sys
import django

# Setup Django environment
sys.path.append('d:/Ongoing/tutedudes/ecom')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecom.settings')
django.setup()

from ecomApp.intelligent_assistant import IntelligentRetailerAssistant
from ecomApp.models import CustomUser, Product, Category, Cart, CartItem
from django.contrib.auth.hashers import make_password

def create_test_data():
    """Create test data for comprehensive testing"""
    print("🔧 Setting up test data...")
    
    # Create test categories
    categories = ['Vegetables', 'Fruits', 'Grains', 'Dairy', 'Spices']
    for cat_name in categories:
        Category.objects.get_or_create(name=cat_name)
    
    # Create test vendors
    vendors = [
        {'username': 'freshfarms', 'email': 'fresh@farms.com'},
        {'username': 'organicstore', 'email': 'organic@store.com'},
        {'username': 'localmarket', 'email': 'local@market.com'}
    ]
    
    for vendor_data in vendors:
        vendor, created = CustomUser.objects.get_or_create(
            username=vendor_data['username'],
            defaults={
                'email': vendor_data['email'],
                'password': make_password('testpass123'),
                'is_vendor': True
            }
        )
    
    # Create test retailer
    retailer, created = CustomUser.objects.get_or_create(
        username='testretailer',
        defaults={
            'email': 'retailer@test.com',
            'password': make_password('testpass123'),
            'is_retailer': True
        }
    )
    
    # Create test products
    test_products = [
        # Vegetables
        {'name': 'Fresh Tomatoes', 'vendor': 'freshfarms', 'category': 'Vegetables', 'price': 50.00, 'quantity': 100},
        {'name': 'Organic Onions', 'vendor': 'organicstore', 'category': 'Vegetables', 'price': 30.00, 'quantity': 80},
        {'name': 'Green Beans', 'vendor': 'localmarket', 'category': 'Vegetables', 'price': 40.00, 'quantity': 60},
        
        # Fruits
        {'name': 'Red Apples', 'vendor': 'freshfarms', 'category': 'Fruits', 'price': 120.00, 'quantity': 50},
        {'name': 'Bananas', 'vendor': 'organicstore', 'category': 'Fruits', 'price': 60.00, 'quantity': 40},
        {'name': 'Fresh Oranges', 'vendor': 'localmarket', 'category': 'Fruits', 'price': 80.00, 'quantity': 35},
        
        # Grains
        {'name': 'Basmati Rice', 'vendor': 'freshfarms', 'category': 'Grains', 'price': 150.00, 'quantity': 200},
        {'name': 'Whole Wheat', 'vendor': 'organicstore', 'category': 'Grains', 'price': 45.00, 'quantity': 150},
        
        # Dairy
        {'name': 'Fresh Milk', 'vendor': 'localmarket', 'category': 'Dairy', 'price': 25.00, 'quantity': 30},
        {'name': 'Greek Yogurt', 'vendor': 'organicstore', 'category': 'Dairy', 'price': 85.00, 'quantity': 20},
        
        # Spices
        {'name': 'Turmeric Powder', 'vendor': 'freshfarms', 'category': 'Spices', 'price': 35.00, 'quantity': 25},
        {'name': 'Red Chili Powder', 'vendor': 'localmarket', 'category': 'Spices', 'price': 40.00, 'quantity': 30}
    ]
    
    for product_data in test_products:
        vendor = CustomUser.objects.get(username=product_data['vendor'])
        category = Category.objects.get(name=product_data['category'])
        
        Product.objects.get_or_create(
            name=product_data['name'],
            vendor=vendor,
            defaults={
                'category': category,
                'price': product_data['price'],
                'quantity': product_data['quantity'],
                'available': True,
                'description': f"High quality {product_data['name'].lower()}"
            }
        )
    
    print("✅ Test data created successfully!")
    return retailer

def test_ai_assistant():
    """Comprehensive test suite for the Intelligent Assistant"""
    print("\n🤖 Starting Intelligent Assistant Tests...\n")
    
    # Setup test data
    retailer = create_test_data()
    assistant = IntelligentRetailerAssistant()
    
    # Test cases with expected behaviors
    test_cases = [
        # Basic listing operations
        {
            'query': 'list all vendors',
            'description': 'List Vendors Test',
            'expected_keywords': ['freshfarms', 'organicstore', 'localmarket', 'products available']
        },
        {
            'query': 'show me all products',
            'description': 'List Products Test',
            'expected_keywords': ['Available Products', 'Fresh Tomatoes', 'Red Apples']
        },
        
        # Price filtering
        {
            'query': 'products under ₹50',
            'description': 'Price Filter Test',
            'expected_keywords': ['under ₹50', 'Organic Onions', 'Green Beans']
        },
        {
            'query': 'budget ₹100',
            'description': 'Budget Filter Test',
            'expected_keywords': ['under ₹100', 'Fresh Tomatoes']
        },
        
        # Category filtering
        {
            'query': 'show vegetables',
            'description': 'Category Filter Test',
            'expected_keywords': ['Vegetables Products', 'Tomatoes', 'Onions']
        },
        {
            'query': 'list fruits',
            'description': 'Fruits Category Test',
            'expected_keywords': ['Fruits Products', 'Apples', 'Bananas']
        },
        
        # Vendor-specific queries
        {
            'query': 'products from freshfarms',
            'description': 'Vendor Filter Test',
            'expected_keywords': ['Products from freshfarms', 'Fresh Tomatoes', 'Red Apples']
        },
        {
            'query': 'what does organicstore sell',
            'description': 'Vendor Products Query',
            'expected_keywords': ['Products from organicstore', 'Organic Onions', 'Bananas']
        },
        
        # Product details and stock
        {
            'query': 'stock of tomatoes',
            'description': 'Stock Check Test',
            'expected_keywords': ['Stock Status', 'Fresh Tomatoes', 'In Stock', '100 units']
        },
        {
            'query': 'tell me about rice',
            'description': 'Product Details Test',
            'expected_keywords': ['Basmati Rice', '₹150', 'freshfarms']
        },
        
        # Cart operations
        {
            'query': 'add tomatoes to cart',
            'description': 'Add to Cart Test',
            'expected_keywords': ['Added to Cart', 'Fresh Tomatoes', 'added successfully']
        },
        {
            'query': 'show my cart',
            'description': 'Cart Status Test',
            'expected_keywords': ['Your Cart', 'Fresh Tomatoes', 'Total']
        },
        
        # Price comparison and cheapest options
        {
            'query': 'cheapest fruits',
            'description': 'Cheapest Options Test',
            'expected_keywords': ['Cheapest Fruits Options', 'Bananas', '₹60']
        },
        {
            'query': 'compare prices for milk',
            'description': 'Price Comparison Test',
            'expected_keywords': ['Price Comparison', 'Fresh Milk', '₹25']
        },
        
        # Vendor information
        {
            'query': 'about vendor freshfarms',
            'description': 'Vendor Info Test',
            'expected_keywords': ['Vendor: freshfarms', 'fresh@farms.com', 'Products:']
        },
        
        # Recommendations
        {
            'query': 'recommend products',
            'description': 'Recommendations Test',
            'expected_keywords': ['Recommended', 'Products', 'add', 'cart']
        },
        
        # Complex queries
        {
            'query': 'vegetables under ₹45',
            'description': 'Complex Filter Test',
            'expected_keywords': ['under ₹45', 'Organic Onions', 'Green Beans']
        },
        
        # Edge cases
        {
            'query': 'products from nonexistentvendor',
            'description': 'Non-existent Vendor Test',
            'expected_keywords': ['not found', 'nonexistentvendor']
        },
        {
            'query': 'xyz random query',
            'description': 'Unknown Query Test',
            'expected_keywords': ['not sure how to help', 'what I can do']
        }
    ]
    
    # Run tests
    passed_tests = 0
    total_tests = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"🧪 Test {i}/{total_tests}: {test_case['description']}")
        print(f"   Query: \"{test_case['query']}\"")
        
        try:
            response = assistant.process_query(test_case['query'], retailer)
            
            # Check if expected keywords are in response
            keywords_found = []
            keywords_missing = []
            
            for keyword in test_case['expected_keywords']:
                if keyword.lower() in response.lower():
                    keywords_found.append(keyword)
                else:
                    keywords_missing.append(keyword)
            
            # Determine test result
            if len(keywords_found) >= len(test_case['expected_keywords']) * 0.6:  # 60% threshold
                print(f"   ✅ PASSED - Found {len(keywords_found)}/{len(test_case['expected_keywords'])} keywords")
                passed_tests += 1
            else:
                print(f"   ❌ FAILED - Found {len(keywords_found)}/{len(test_case['expected_keywords'])} keywords")
                print(f"   Missing: {keywords_missing}")
            
            print(f"   Response: {response[:100]}...\\n")
            
        except Exception as e:
            print(f"   ❌ ERROR: {str(e)}\\n")
    
    # Test summary
    print(f"\n📊 Test Results Summary:")
    print(f"   Passed: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)")
    print(f"   Failed: {total_tests - passed_tests}/{total_tests}")
    
    if passed_tests >= total_tests * 0.8:  # 80% pass rate
        print(f"   🎉 Overall Status: EXCELLENT - AI Assistant is production ready!")
    elif passed_tests >= total_tests * 0.6:  # 60% pass rate
        print(f"   ✅ Overall Status: GOOD - AI Assistant works well with minor improvements needed")
    else:
        print(f"   ⚠️ Overall Status: NEEDS IMPROVEMENT - Significant issues detected")
    
    return passed_tests, total_tests

def demonstrate_advanced_features():
    """Demonstrate advanced AI assistant features"""
    print("\n🚀 Advanced Features Demonstration:\n")
    
    retailer = CustomUser.objects.get(username='testretailer')
    assistant = IntelligentRetailerAssistant()
    
    advanced_queries = [
        "I want to buy vegetables under ₹40",
        "Show me the cheapest dairy products",
        "What's the most expensive item from organicstore?",
        "Add bananas and milk to my cart",
        "Compare prices for all grains",
        "Recommend products based on my budget of ₹200"
    ]
    
    for query in advanced_queries:
        print(f"🔍 Query: \"{query}\"")
        response = assistant.process_query(query, retailer)
        print(f"🤖 Response: {response}\\n")
        print("-" * 80 + "\\n")

if __name__ == "__main__":
    print("🎯 Intelligent Retailer Assistant - Comprehensive Test Suite")
    print("=" * 60)
    
    # Run main test suite
    passed, total = test_ai_assistant()
    
    # Demonstrate advanced features
    demonstrate_advanced_features()
    
    print("\\n🏁 Testing Complete!")
    print(f"Final Score: {passed}/{total} tests passed")
