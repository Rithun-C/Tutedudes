from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'quantity', 'image', 'available']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            # Apply Bootstrap classes to widgets for consistent styling
            if isinstance(field.widget, (forms.CheckboxInput,)):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, (forms.Select,)):
                field.widget.attrs.update({'class': 'form-select'})
            else:
                existing = field.widget.attrs.get('class', '')
                field.widget.attrs.update({'class': f'{existing} form-control'.strip()})
