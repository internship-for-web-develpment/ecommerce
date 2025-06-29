from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
from functools import wraps
from  decimal import Decimal

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# MySQL config
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'ecommerce'

mysql = MySQL(app)


@app.route('/')
def index():
    return render_template('index.html')


# Registration
@app.route('/register', methods=['POST'])
def register():
    email = request.form['username']
    password = request.form['password']
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM sign WHERE email = %s", (email,))
    account = cursor.fetchone()

    if account:
        return "Email already registered. Please login."
    else:
        cursor.execute("INSERT INTO sign (email, password) VALUES (%s, %s)", (email, password))
        mysql.connection.commit()
        return redirect(url_for('index'))


# Login
@app.route('/login', methods=['POST'])
def login():
    email = request.form['username']
    password = request.form['password']
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM sign WHERE email = %s AND password = %s", (email, password))
    user = cursor.fetchone()

    if user:
        session['email'] = email
        return redirect(url_for('product'))
    else:
        return "Invalid email or password"


# Logout
@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('index'))


# Login required decorator
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'email' not in session:
            return redirect(url_for('index'))
        return func(*args, **kwargs)

    return wrapper


# Home page
@app.route('/home')
def home():
    return render_template('home_page.html')


# Product detail page
@app.route('/product_detail/<int:product_id>')
@login_required
def product_detail(product_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product = cursor.fetchone()
    cursor.close()
    if not product:
        return "Product not found", 404
    return render_template("product_detail.html", product=product)


# Product list page
@app.route('/product')
@login_required
def product():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    cursor.close()
    return render_template('product.html', products=products)


# Men’s page
@app.route('/men')
def men():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM products WHERE category = 'men' LIMIT 7")
    products = cursor.fetchall()
    cursor.close()
    repeated_products = products * 10
    return render_template('men.html', products=repeated_products)


# Women’s page
@app.route('/women')
def women():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM products WHERE category = 'women' LIMIT 7")
    products = cursor.fetchall()
    cursor.close()
    repeated_products = products * 10
    return render_template('women.html', products=repeated_products)


# Kids’ page
@app.route('/kids')
def kids():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM products WHERE category = 'kids' LIMIT 7")
    products = cursor.fetchall()
    cursor.close()
    repeated_products = products * 10
    return render_template('kids.html', products=repeated_products)


# Cart page
@app.route('/cart')
@login_required
def cart():
    email = session['email']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('''
        SELECT cart.id, products.name, products.image, products.price, cart.quantity
        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.email = %s
    ''', (email,))
    items = cursor.fetchall()
    tax_rate = Decimal('0.18')  # Pass this to template
    cursor.close()
    return render_template('cart.html', cart_items=items, tax_rate=tax_rate)



# Add to Cart Route
@app.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    product_id = request.form['product_id']
    quantity = 1
    email = session['email']
    cursor = mysql.connection.cursor()
    # Check if item already in cart
    cursor.execute("SELECT * FROM cart WHERE email = %s AND product_id = %s", (email, product_id))
    item = cursor.fetchone()

    if item:
        cursor.execute("UPDATE cart SET quantity = quantity + 1 WHERE email = %s AND product_id = %s",
                       (email, product_id))
    else:
        cursor.execute("INSERT INTO cart (email, product_id, quantity) VALUES (%s, %s, %s)",
                       (email, product_id, quantity))

    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('cart'))

@app.route('/update_quantity', methods=['POST'])
@login_required
def update_quantity():
    item_id = request.form['item_id']
    action = request.form['action']
    cursor = mysql.connection.cursor()

    if action == 'increase':
        cursor.execute("UPDATE cart SET quantity = quantity + 1 WHERE id = %s", (item_id,))
    elif action == 'decrease':
        cursor.execute("UPDATE cart SET quantity = GREATEST(quantity - 1, 1) WHERE id = %s", (item_id,))

    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('cart'))



@app.route('/remove_from_cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    email = session['email']
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM cart WHERE id = %s AND email = %s", (item_id, email))
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('cart'))


# Address, Order, Payment pages
@app.route('/address', methods=['GET', 'POST'])
def address():
    if 'email' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'use_selected':
            selected_address_id = request.form.get('selected_address_id')

            # Deselect all for current user
            cursor.execute("UPDATE address SET selected = FALSE WHERE email = %s", (session['email'],))

            # Mark chosen address as selected
            cursor.execute("UPDATE address SET selected = TRUE WHERE id = %s AND email = %s", (selected_address_id, session['email']))
            mysql.connection.commit()
            return redirect(url_for('order_summary'))

        elif action == 'add_new':
            name = request.form['name']
            phone = request.form['phone']
            address_text = request.form['address']

            cursor.execute("INSERT INTO address (email, name, phone, address, selected) VALUES (%s, %s, %s, %s, %s)",
                           (session['email'], name, phone, address_text, True))

            # Deselect all other addresses
            cursor.execute("UPDATE address SET selected = FALSE WHERE email = %s AND id != LAST_INSERT_ID()", (session['email'],))
            mysql.connection.commit()
            return redirect(url_for('order_summary'))

    # GET: Show all addresses
    cursor.execute("SELECT * FROM address WHERE email = %s", (session['email'],))
    saved_addresses = cursor.fetchall()
    return render_template('address.html', saved_addresses=saved_addresses)



@app.route('/save_address', methods=['POST'])
@login_required
def save_address():
    name = request.form['name']
    phone = request.form['phone']
    address = request.form['address']
    email = session['email']

    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO address (email, name, phone, address) VALUES (%s, %s, %s, %s)",
                   (email, name, phone, address))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('order_summary'))  # or 'payment'




@app.route('/order-summary')
def order_summary():
    if 'email' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get selected address
    cursor.execute("SELECT * FROM address WHERE email = %s AND selected = TRUE", (session['email'],))
    selected_address = cursor.fetchone()

    # Get cart items
    cursor.execute('''
                   SELECT products.name, products.price, cart.quantity
                   FROM cart
                            JOIN products ON cart.product_id = products.id
                   WHERE cart.email = %s
                   ''', (session['email'],))
    cart_items = cursor.fetchall()

    subtotal = sum(float(item['price']) * int(item['quantity']) for item in cart_items)

    tax = subtotal * 0.18
    total = subtotal + tax + 50

    return render_template('order-summary.html', selected_address=selected_address, cart_items=cart_items,
                           subtotal=subtotal, tax=tax, total=total)


@app.route('/payment', methods=['GET', 'POST'])
@login_required
def payment():
    if request.method == 'POST':
        # handle payment form submission here
        return redirect(url_for('home'))  # or 'order_success'
    return render_template('payment.html')



if __name__ == '__main__':
    app.run(debug=True)
