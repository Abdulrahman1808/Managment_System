import customtkinter as ctk
from tkinter import ttk, messagebox
from ui_elements import show_error, show_success
from data_handler import load_data, save_data, get_next_id, import_from_excel
from theme import (
    COLORS, FONTS, create_styled_button,
    create_styled_entry, create_styled_frame,
    create_styled_label
)
from datetime import datetime
# Import for image handling
import os
from PIL import Image

class RecordSale:
    def __init__(self, root, current_language, languages, back_callback):
        self.root = root
        self.current_language = current_language
        self.LANGUAGES = languages
        self.back_callback = back_callback
        self.cart = []
        # Load products initially, but don't display until record_sale is called
        self.products = load_data("products") or []
        self.products = [p for p in self.products if p.get('status', 'Active') == 'Active']

    def refresh_products(self):
        """Refresh the products list from database and update display"""
        import traceback
        try:
            # Load products from database
            all_products = load_data("products") or []
            print(f"[DEBUG] Loaded products count: {len(all_products)}")
            print(f"[DEBUG] Loaded products: {all_products}")
            # Filter out deleted or inactive products
            self.products = [p for p in all_products if p.get('status', 'Active') == 'Active']
            print(f"[DEBUG] Active products count: {len(self.products)}")
            print(f"[DEBUG] Active products: {self.products}")
            
            # If the UI frames exist, update them
            if hasattr(self, 'products_frame') and self.products_frame.winfo_exists():
                # Clear current products
                for widget in self.products_frame.winfo_children():
                    widget.destroy()
                
                # Check if there are active products to display
                if not self.products:
                    no_products_label = create_styled_label(
                        self.products_frame,
                        text=self.LANGUAGES[self.current_language].get("no_active_products", "No active products found."),
                        style='body'
                    )
                    no_products_label.pack(pady=20)
                else:
                    # Add products to display
                    for product in self.products:
                        try:
                            product_frame = create_styled_frame(self.products_frame, style='card')
                            product_frame.pack(fill='x', padx=10, pady=5)
                            
                            # Image display
                            image_path = product.get('image_path')
                            if image_path and os.path.exists(image_path):
                                try:
                                    img = Image.open(image_path)
                                    img.thumbnail((50, 50)) # Resize for list view
                                    # Use CTkImage for compatibility with customtkinter
                                    img_tk = ctk.CTkImage(light_image=img, dark_image=img, size=(50, 50))
                                    image_label = ctk.CTkLabel(product_frame, image=img_tk, text="")
                                    image_label.image = img_tk # Keep a reference!
                                except Exception as e:
                                    print(f"[ERROR] Could not load product image {image_path}: {e}")
                                    image_label = create_styled_label(product_frame, text=self.LANGUAGES[self.current_language].get("error_loading_image", "Error loading image"), style='small')
                            else:
                                 image_label = create_styled_label(product_frame, text=self.LANGUAGES[self.current_language].get("no_image", "No Image"), style='small')

                            image_label.pack(side='left', padx=10, pady=5) # Pack image to the left

                            # Product details
                            details_frame = create_styled_frame(product_frame, style='card')
                            details_frame.pack(side='left', fill='x', expand=True, padx=(0, 10), pady=10) # Pack details next to image
                            
                            name_label = create_styled_label(
                                details_frame,
                                text=product.get('name', ''),
                                style='subheading'
                            )
                            name_label.pack(side='left', padx=10)
                            
                            price_label = create_styled_label(
                                details_frame,
                                text=f"${float(product.get('price', 0) or 0):.2f}",
                                style='body'
                            )
                            price_label.pack(side='left', padx=10)
                            
                            # Add to cart button
                            add_button = create_styled_button(
                                product_frame,
                                text=self.LANGUAGES[self.current_language].get("add_to_cart", "Add to Cart"),
                                style='primary',
                                width=120,
                                command=lambda p=product: self.add_to_cart(p)
                            )
                            add_button.pack(side='right', padx=10, pady=10)
                        except Exception as e:
                            print(f"[DEBUG] Error adding product: {e}")
                    
                    # Update cart display as well if it exists and the cart is not empty
                    if hasattr(self, 'cart_frame') and self.cart_frame.winfo_exists():
                         self.update_cart_display()
                    
        except Exception as e:
            import traceback
            traceback_str = traceback.format_exc()
            print(f"[TRACEBACK] {traceback_str}")
            show_error(f"Error refreshing products: {str(e)}", self.current_language)

    def update_cart_display(self):
        """Update the cart display with current items"""
        try:
            # Only update if the cart frame exists and is visible
            if hasattr(self, 'cart_frame') and self.cart_frame.winfo_exists():
                # Clear current items
                for widget in self.cart_frame.winfo_children():
                    widget.destroy()
                    
                # Add cart items
                for item in self.cart:
                    item_frame = create_styled_frame(self.cart_frame, style='card')
                    item_frame.pack(fill='x', padx=10, pady=5)
                    
                    # Product name and quantity
                    name_label = create_styled_label(
                        item_frame,
                        text=f"{item['product'].get('name', '')} x {item['quantity']}",
                        style='body'
                    )
                    name_label.pack(side='left', padx=10, pady=5)
                    
                    # Price
                    price = float(item['product'].get('price', 0))
                    price_label = create_styled_label(
                        item_frame,
                        text=f"${price * item['quantity']:.2f}",
                        style='body'
                    )
                    price_label.pack(side='right', padx=10, pady=5)
                    
                    # Remove button
                    remove_btn = create_styled_button(
                        item_frame,
                        text="×",
                        style='outline',
                        width=30,
                        command=lambda i=item: self.remove_from_cart(i)
                    )
                    remove_btn.pack(side='right', padx=5, pady=5)
                
                # Calculate totals
                subtotal = sum(float(item['product'].get('price', 0)) * item['quantity'] for item in self.cart)
                total = subtotal
                
                # Update total labels
                if hasattr(self, 'subtotal_value') and self.subtotal_value.winfo_exists():
                    self.subtotal_value.configure(text=f"${subtotal:.2f}")
                if hasattr(self, 'total_value') and self.total_value.winfo_exists():
                    self.total_value.configure(text=f"${total:.2f}")
                    
        except Exception as e:
            show_error(f"Error updating cart display: {str(e)}", self.current_language)

    def record_sale(self):
        """Create a modern sales recording interface"""
        # Clear current frame
        for widget in self.root.winfo_children():
            widget.destroy()
            
        # Create main container
        main_frame = create_styled_frame(self.root, style='section')
        main_frame.pack(fill='both', expand=True)
        
        # Header
        header_frame = create_styled_frame(main_frame, style='card')
        header_frame.pack(fill='x', padx=20, pady=20)
        
        back_button = create_styled_button(
            header_frame,
            text=self.LANGUAGES[self.current_language].get("back", "Back"),
            style='outline',
            command=self.back_callback
        )
        back_button.pack(side='left', padx=20, pady=20)
        
        title_label = create_styled_label(
            header_frame,
            text=self.LANGUAGES[self.current_language].get("record_sale", "Record Sale"),
            style='heading'
        )
        title_label.pack(side='left', padx=20, pady=20)
        
        # Refresh button
        refresh_button = create_styled_button(
            header_frame,
            text=self.LANGUAGES[self.current_language].get("refresh", "Refresh"),
            style='outline',
            command=self.refresh_products
        )
        refresh_button.pack(side='right', padx=20, pady=20)
        
        # Main content area
        content_frame = create_styled_frame(main_frame, style='card')
        content_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        # Left side - Product selection
        left_frame = create_styled_frame(content_frame, style='card')
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10), pady=20)
        
        # Barcode entry section
        barcode_frame = create_styled_frame(left_frame, style='card')
        barcode_frame.pack(fill='x', padx=20, pady=(0, 10))
        barcode_label_text = ("Barcode / باركود" if self.current_language == 'en' else "باركود / Barcode")
        barcode_label = create_styled_label(
            barcode_frame,
            text=barcode_label_text,
            style='body'
        )
        barcode_label.pack(side='left', padx=10, pady=10)
        self.barcode_entry = create_styled_entry(
            barcode_frame,
            placeholder_text=barcode_label_text
        )
        self.barcode_entry.pack(side='left', padx=10, pady=10, fill='x', expand=True)
        self.barcode_entry.bind('<Return>', self.handle_barcode_entry)
        
        # Search section
        search_frame = create_styled_frame(left_frame, style='card')
        search_frame.pack(fill='x', padx=20, pady=(0, 20))
        
        search_entry = create_styled_entry(
            search_frame,
            placeholder_text=self.LANGUAGES[self.current_language].get("search_products", "Search products...")
        )
        search_entry.pack(side='left', padx=20, pady=20, fill='x', expand=True)
        
        # Products list
        self.products_frame = ctk.CTkScrollableFrame(left_frame, orientation='vertical')
        self.products_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        # Initial display of products - now happens after frame creation
        self.refresh_products()
        
        # Right side - Shopping cart
        right_frame = create_styled_frame(content_frame, style='card')
        right_frame.pack(side='right', fill='both', expand=True, padx=(10, 0), pady=20)
        
        cart_title = create_styled_label(
            right_frame,
            text=self.LANGUAGES[self.current_language].get("shopping_cart", "Shopping Cart"),
            style='heading'
        )
        cart_title.pack(pady=20)
        
        # Cart items
        self.cart_frame = ctk.CTkScrollableFrame(right_frame, orientation='vertical')
        self.cart_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        # Initial display of cart items - now happens after frame creation
        self.update_cart_display()
        
        # Cart summary
        summary_frame = create_styled_frame(right_frame, style='card')
        summary_frame.pack(fill='x', padx=20, pady=(0, 20))
        
        # Subtotal
        subtotal_label = create_styled_label(
            summary_frame,
            text=self.LANGUAGES[self.current_language].get("subtotal", "Subtotal:"),
            style='subheading'
        )
        subtotal_label.pack(side='left', padx=20, pady=20)
        
        self.subtotal_value = create_styled_label(
            summary_frame,
            text="$0.00",
            style='heading'
        )
        self.subtotal_value.pack(side='right', padx=20, pady=20)
        
        # Total
        total_label = create_styled_label(
            summary_frame,
            text=self.LANGUAGES[self.current_language].get("total", "Total:"),
            style='subheading'
        )
        total_label.pack(side='left', padx=20, pady=20)
        
        self.total_value = create_styled_label(
            summary_frame,
            text="$0.00",
            style='heading'
        )
        self.total_value.pack(side='right', padx=20, pady=20)
        
        # Checkout button
        checkout_button = create_styled_button(
            right_frame,
            text=self.LANGUAGES[self.current_language].get("checkout", "Checkout"),
            style='primary',
            command=self.checkout
        )
        checkout_button.pack(pady=20)

    def add_to_cart(self, product):
        """Add a product to the cart"""
        try:
            # Check if product is already in cart
            for item in self.cart:
                # Ensure 'id' exists in product dictionary
                if item['product'].get('id') == product.get('id'):
                    item['quantity'] += 1
                    self.update_cart_display()
                    return

            # Add new item to cart
            self.cart.append({
                'product': product,
                'quantity': 1
            })
            self.update_cart_display()
        except Exception as e:
            show_error(f"Error adding to cart: {str(e)}", self.current_language)

    def remove_from_cart(self, item):
        """Remove an item from the cart"""
        try:
            self.cart.remove(item)
            self.update_cart_display()
        except Exception as e:
            show_error(f"Error removing from cart: {str(e)}", self.current_language)

    def checkout(self):
        """Process the sale"""
        try:
            if not self.cart:
                show_error(self.LANGUAGES[self.current_language].get("empty_cart", "Cart is empty"), self.current_language)
                return

            # Create sale record
            sale = {
                'id': get_next_id('sales'),
                'items': self.cart,
                'total': sum(float(item['product'].get('price', 0)) * item['quantity'] for item in self.cart),
                'date': str(datetime.now())
            }
            
            # Save sale
            sales = load_data("sales") or []
            sales.append(sale)
            save_data("sales", sales)
            
            # Update inventory - ensure quantity is a number before subtracting
            inventory_updated = False
            products_to_update = load_data("products") or [] # Load current products for inventory update

            for item in self.cart:
                 # Find the product in the current products list to update its quantity
                for product in products_to_update:
                     if product.get('id') == item['product'].get('id'):
                         # Ensure quantity is a number before subtracting
                         current_quantity = product.get('quantity', 0)
                         if isinstance(current_quantity, (int, float)):
                            product['quantity'] = current_quantity - item['quantity']
                            inventory_updated = True
                            break
                         else:
                            show_error(f"Error updating inventory: Invalid quantity for product {product.get('name','')}", self.current_language)
                            # Optionally, decide whether to proceed with the sale if inventory update fails for one item
                            # For now, let's just log the error and continue with other items

            if inventory_updated:
                 save_data("products", products_to_update) # Save the updated products list back to database

            # Clear cart and show success message
            self.cart = []
            self.update_cart_display()
            show_success(self.LANGUAGES[self.current_language].get("sale_recorded", "Sale recorded successfully"), self.current_language)

        except Exception as e:
            show_error(f"Error processing checkout: {str(e)}", self.current_language)

    def handle_barcode_entry(self, event=None):
        """Handle barcode entry and add product to cart if found"""
        barcode = self.barcode_entry.get().strip()
        if not barcode:
            return
        # ابحث عن المنتج بالباركود
        found_product = None
        for product in self.products:
            if str(product.get('barcode', '')).strip() == barcode:
                found_product = product
                break
        if found_product:
            self.add_to_cart(found_product)
            self.barcode_entry.delete(0, 'end')
        else:
            show_error(self.LANGUAGES[self.current_language].get("product_not_found", "Product not found"), self.current_language)
            self.barcode_entry.delete(0, 'end')
