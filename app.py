from flask import Flask, request,jsonify,make_response, render_template, redirect, url_for, session, flash
from peewee import *
from modules import * 
from weasyprint import HTML
import time
import requests
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
db = SqliteDatabase('invoice.db')
app.secret_key = "your_secret_key_here"

@app.route('/customer-create')
def customer_create():
    return render_template('customer.html')

@app.route('/customer', methods=['GET', 'POST', 'PUT', 'DELETE'])
def customer():
    if request.method == 'POST':
        data = request.form
        username = data.get("username")
        email = data.get("email")
        address = data.get("address")

        if username is None or not username:
            return "please provide username"
        if email is None or not email:
            return "Must be provide email"
        
        customer= Customer.create(
            username=username,
            email=email,
            address=address
        )
        customers = Customer.select()
        return render_template('customer-list.html', customers=customers)
    else:
        customers = Customer.select()
        return render_template('customer-list.html',customers=customers)
  
@app.route("/customer/<int:id>/update", methods=['POST', 'GET'])
def update_customer(id):
    customer = Customer.get_by_id(id)

    if request.method == "POST":
        customer.username = request.form.get("username")
        customer.email = request.form.get("email")
        customer.address = request.form.get("address")
        customer.save()  
        return redirect(url_for('customer'))  

    return render_template("customer-update.html", customer=customer)

@app.route("/customer/<int:id>/delete", methods=['GET','POST', "DELETE"])
def delete_customer(id):
    
    customer = Customer.get_by_id(id)
    if not customer:
        return "<script>alert('Customer Not Found')</script>"
    customer.delete_instance()
    return "<script>alert('Customer Delete Successfully')</script>"

@app.route("/invoice-create")
def invoice_create():
    items = Item.select()
    return render_template('invoice.html', items=items)

@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    search_input = request.args.get('customer','').lower()
    suggestions = [
        {"id": customer.id, "name": customer.username}
        for customer in Customer.select()
        if search_input in customer.username.lower()
    ]
    return jsonify(matching_results=suggestions)

@app.route("/invoice", methods=['POST', 'GET'])
def invoice():
    if request.method == "POST":
        data = request.form
        invoice_number = data.get("invoice_number")
        customer_id = data.get("customer")  
        invoice_date = data.get("invoice_date")
        total_amount = data.get("total_amount")

        item_names = data.getlist("item_name[]")
        qtys = data.getlist("qty[]")
        prices = data.getlist("price[]")

        if not customer_id:
            return render_template("invoice-create.html", alert="Please enter customer")
        if not invoice_number:
            return render_template("invoice-create.html", alert="Please provide invoice number")
        if not item_names:
            return render_template("invoice-create.html", alert="No items added")


        customer = Customer.get_by_id(int(customer_id))


        invoice = Invoice.create(
            invoice_number=invoice_number,
            customer=customer,
            total_amount=total_amount,
            invoice_date=invoice_date
        )

        for name, qty, price in zip(item_names, qtys, prices):
            Item.create(
                invoice=invoice,
                item_name=name,
                quantity=int(qty),
                unit_price=float(price)
            )

        invoices = Invoice.select()
        return render_template("invoice-list.html", invoices=invoices)

    else:
        invoices = Invoice.select()
        return render_template("invoice-list.html", invoices=invoices)


@app.route("/invoice/<string:invoice_number>/update", methods=['POST','GET'])
def update_invoice(invoice_number):
    invoice = Invoice.get_or_none(Invoice.invoice_number == invoice_number)
    if not invoice:
        return render_template("invoice-list.html", alert="Invoice not found!")

    if request.method == "POST": 
        customer_id = request.form.get("customer")
        if customer_id:
            invoice.customer = Customer.get_by_id(customer_id)

        invoice.total_amount = request.form.get("total_amount")
        invoice.invoice_date = request.form.get("invoice_date")
        invoice.save()

      
        item_ids = request.form.getlist("item_id[]")   
        item_names = request.form.getlist("item_name[]")
        qtys = request.form.getlist("qty[]")
        prices = request.form.getlist("price[]")

        for item_id, name, qty, price in zip(item_ids, item_names, qtys, prices):
            item = Item.get_or_none(Item.id == item_id)
            if item:
                item.item_name = name
                item.quantity = int(qty)
                item.unit_price = float(price)
                item.save()

        return redirect(url_for('invoice'))

    items = Item.select().where(Item.invoice == invoice)
    return render_template('invoice-update.html', invoice=invoice, items=items)

@app.route("/invoice/<string:invoice_number>/delete",methods=['GET','POST', 'DELETE'])
def delete_invoice(invoice_number):
    invoice = Invoice.get_or_none(Invoice.invoice_number == invoice_number)
    if not invoice:
        return "invoice_number not found!"
    invoice.delete_instance()
    invoices = Invoice.select()
    return render_template('invoice-list.html', invoices=invoices)



@app.route("/invoices/<string:invoice_number>/pdf", methods=["GET"])
def invoice_pdf(invoice_number):
    try:
        invoice = Invoice.get(Invoice.invoice_number == invoice_number)  
        customer = invoice.customer
        items = Item.select().where(Item.invoice == invoice)

        html = f"""
        <h1>Invoice : {invoice.invoice_number}</h1>
        <p>Customer: {customer.username}</p>
        <p>{customer.email}</p>
        <table border="1">
        <tr><th>Item</th><th>Qty</th><th>Unit Price</th><th>Amount</th></tr>
        """
        for item in items:
            html += f"<tr><td>{item.item_name}</td><td>{item.quantity}</td><td>{item.unit_price}</td></tr>"
        html += f"</table><p>Total: ₹{invoice.total_amount}</p>"

        pdf = HTML(string=html).write_pdf()
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        return response
    except Invoice.DoesNotExist:
        return jsonify({"error": "Invoice not found"}), 404


@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmed = request.form.get("confirmed")

        if not username:
            flash("Must enter a username!", "error")
            return redirect(url_for("register"))

        if password != confirmed:
            flash("Passwords do not match!", "error")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)
        
        Users.create(username=username, password=hashed_password)

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        try:
            user = Users.get(Users.username == username)
            if check_password_hash(user.password, password):
                session["user_id"] = user.id
                session["username"] = user.username
                flash(f"Welcome, {user.username}!", "success")
                return redirect(url_for("home"))
            else:
                flash("Incorrect password!", "error")
                return redirect(url_for("login"))
        except Users.DoesNotExist:
            flash("User does not exist!", "error")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

api_url = "https://buildwithhussain.com/api/v2/method/get_arn_number"

headers = {
    "Authorization": "token 2c70587e2df4779:56331804ac8ca7b",
    "Content-Type": "application/json"
}




def send_post_method(api_url, headers, data_payload):
    response = requests.post(api_url, headers=headers, json=data_payload)
    if response.status_code == 200:
        response.raise_for_status()
        print("Response:", response.json())
        return response.json()
    
    else:
        print(f"Request failed with status code: {response.status_code}")
        print(response.text)
        return None


def retry_logic(api_url, headers, data_payload, maxRetries=3, interval=1):
    for attempt in range(1, maxRetries+1):
        try:
            response = requests.post(api_url, headers, json=data_payload)
            response.raise_for_status()
            return response.json()
        except:
            print(f"Attempt{attempt}/{maxRetries}")
            if attempt < maxRetries:
                times = interval * (2 ** (attempt-1))
                print(f'Retrying in {times}')
                time.sleep(times)
    raise Exception(f"POST request failed after {maxRetries} attempts.")

@app.route('/api/arn_generation/<string:invoice_number>')
def arn_generation(invoice_number):


    try:
        invoice = Invoice.get(Invoice.invoice_number == invoice_number)
        customer = invoice.customer
    except Invoice.DoesNotExist:
        return jsonify({"error":"Invoice not found"}),404
   
    data_payload = {
        "user_name": customer.username,
        "invoice_number":invoice.invoice_number
    }
    
    
    response_data = send_post_method(api_url, headers, data_payload)
    if not response_data:
        try:
            response_data = retry_logic(api_url, headers, data_payload)
        except Exception as e:
            return jsonify({"error": str(e)}), 500


    arn_number = response_data.get("arn_number")
    if arn_number:
        invoice.arn_number = arn_number
        invoice.save()
    else:
        return jsonify({"error": "arn_number not found in API response"}), 400

    return jsonify({
        "message": "ARN saved successfully",
        "arn_number": arn_number
    }), 200
@app.route("/api/dashboard")
def dashboard_data():
    data = {
        "total_invoices": 12,
        "total_customers": 5,
        "total_amount": 4500.75,
        "paid_amount": 3200.50
    }
    return jsonify(data)

@app.route('/')
def home():
    if "user_id" not in session:
        flash("Please login first!", "error")
        return redirect(url_for("login"))

    total_customers = Customer.select().count()
    total_invoices = Invoice.select().count()

    from peewee import fn
    total_amount = Invoice.select(fn.SUM(Invoice.total_amount)).scalar() or 0
    
    
    return render_template(
        "home.html",
        username=session["username"],
        total_customers=total_customers,
        total_invoices=total_invoices,
        total_amount=total_amount
    )

if __name__ == "__main__":
    app.run(debug=True)