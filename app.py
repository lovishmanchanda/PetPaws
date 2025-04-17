from flask import Flask, render_template, redirect , url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user , login_required, logout_user, current_user
import os
from functools import wraps


app=Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + \
    os.path.join(basedir, "app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config['SECRET_KEY'] = 'your_secret_key'

db = SQLAlchemy(app)

bcrypt = Bcrypt(app) #enable password hashing
login_manager = LoginManager() #initialize login system
login_manager.init_app(app) #Explicitly binds the Loginmaker to the Flask app
login_manager.login_view = 'login' #Redirects unauthorized users to login page

class Pet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    breed = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(255), nullable=True, default="default_pet.jpg")  # Default image if none uploaded
    status = db.Column(db.String(50), default="Available")  # Available, Adopted, etc.
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # Link to User table
    medical_issues = db.Column(db.String(255), nullable=True)  # Any medical issues (Yes/No + Description)
    pet_type = db.Column(db.String(50), nullable=False)  # Dropdown (Dog, Cat, Bird, Horse, Other)
    other_pet_type = db.Column(db.String(100), nullable=True)  # If "Other" is selected
    address = db.Column(db.String(255), nullable=False)  # Pet's location

    owner = db.relationship("User", backref="pets")

    def __repr__(self):
        return f"<Pet {self.name}>"



wishlist = db.Table('wishlist',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('pet_id', db.Integer, db.ForeignKey('pet.id'), primary_key=True)
)


class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    mobile = db.Column(db.String(15), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')
    wishlist_pets = db.relationship('Pet', secondary=wishlist, backref='wishlist_users')


    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password)

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
    
with app.app_context():
    db.create_all()

    # Check if an admin user already exists
    if not User.query.filter_by(role="admin").first():  
        admin_user = User(
            name="Admin",
            email="admin@gmail.com",
            mobile="1234567890",
            role="admin"
        )
        admin_user.set_password("admin123") 

        db.session.add(admin_user)
        db.session.commit()


@app.route('/')
def index():
    return render_template('index.html')


# Route to display pets
@app.route("/pets")
def pets():
    all_pets = Pet.query.all()
    return render_template("pets.html", pets=all_pets)

# setting path for images
UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), "static/images")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure the directory exists

@app.route("/add_pet", methods=["GET", "POST"])
@login_required
def add_pet():
    if request.method == "POST":
        name = request.form["name"]
        breed = request.form["breed"]
        age = request.form["age"]
        description = request.form["description"]
        pet_type = request.form["pet_type"]
        other_pet_type = request.form.get("other_pet_type") if pet_type == "Other" else None
        medical_issues = request.form["medical_issues"]
        address = request.form["address"]

        # Handle Image Upload
        image = request.files["image"]
        image_filename = None  # Default to None if no image uploaded

        if image and image.filename:
            image_filename = os.path.join(UPLOAD_FOLDER, image.filename)
            image.save(image_filename)  # Save image safely
            print("✅ Image saved at:", image_filename)  # Debugging output

        new_pet = Pet(
            name=name,
            breed=breed,
            age=age,
            description=description,
            pet_type=pet_type,
            other_pet_type=other_pet_type,
            medical_issues=medical_issues,
            address=address,
            image_filename=image.filename if image else None,  # Store filename only
            owner_id=current_user.id,
        )

        db.session.add(new_pet)
        db.session.commit()

        flash("Pet added successfully!", "success")
        return redirect(url_for("pets"))

    return render_template("add_pet.html")




# Route to edit pet details (UPDATE)
@app.route("/edit_pet/<int:id>", methods=["GET", "POST"])
@login_required
def edit_pet(id):
    pet = Pet.query.get_or_404(id)

    # Ensure only the owner can edit the pet
    if pet.owner_id != current_user.id:
        flash("You are not authorized to edit this pet.", "danger")
        return redirect(url_for("pets"))

    if request.method == "POST":
        pet.name = request.form["name"]
        pet.breed = request.form["breed"]
        pet.age = request.form["age"]
        pet.description = request.form["description"]
        pet.pet_type = request.form["pet_type"]
        pet.other_pet_type = request.form.get("other_pet_type", None) if pet.pet_type == "Other" else None
        pet.medical_issues = request.form["medical_issues"]
        pet.address = request.form["address"]

        # Handle Image Upload
        image = request.files["image"]
        if image and image.filename:
            image_filename = image.filename
            image.save(os.path.join("static/images", image_filename))
            pet.image_filename = image_filename  # Update image filename only if a new image is uploaded

        db.session.commit()
        flash("Pet details updated successfully!", "success")
        return redirect(url_for("pets"))

    return render_template("edit_pet.html", pet=pet)


# Route to delete a pet (DELETE)
@app.route("/delete_pet/<int:id>")
def delete_pet(id):
    pet = Pet.query.get_or_404(id)
    db.session.delete(pet)
    db.session.commit()
    flash("Pet deleted successfully!", "danger")
    return redirect(url_for("pets"))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("index"))
        else:
            flash("Invalid email or password", "danger")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"]) 
def register(): 
    if request.method == "POST": 
        name = request.form.get("name") 
        email = request.form.get("email") 
        password = request.form.get("password") 
        confirm_password = request.form.get("confirm_password") 
        mobile = request.form.get("mobile")

        # Check if passwords match 
        if password != confirm_password: 
            flash("Passwords do not match!", "danger") 
            return redirect(url_for("register"))
        
        # Check if the email already exists 
        if User.query.filter_by(email=email).first(): 
            flash("Email already exists!", "danger") 
            return redirect(url_for("register"))
        
        new_user = User(name=name, email=email, mobile=mobile) 
        new_user.set_password(password) 
        db.session.add(new_user) 
        db.session.commit()

        flash("Registration successful! Please log in.", "success") 
        return redirect(url_for("login"))
    
    return render_template("/register.html") 


@app.route("/logout") 
@login_required 
def logout(): 
    logout_user() 
    flash("Logged out successfully!", "info") 
    return redirect(url_for("login"))


@app.route("/profile") 
@login_required 
def profile(): 
    return render_template("profile.html", user=current_user)

@app.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        current_user.name = request.form.get("name")
        current_user.mobile = request.form.get("mobile")

        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))

    return render_template("edit_profile.html", user=current_user)


@app.route("/wishlist")
@login_required
def wishlist():
    return render_template("wishlist.html", pets=current_user.wishlist_pets)

@app.route('/wishlist/add/<int:pet_id>')
@login_required
def add_to_wishlist(pet_id):
    pet = Pet.query.get_or_404(pet_id)

    if pet not in current_user.wishlist_pets:  # Use wishlist_pets instead of wishlist
        current_user.wishlist_pets.append(pet)
        db.session.commit()
        flash(f"{pet.name} has been added to your wishlist!", "success")
    else:
        flash(f"{pet.name} is already in your wishlist.", "info")

    return redirect(url_for('wishlist'))

@app.route("/remove_from_wishlist/<int:pet_id>")
@login_required
def remove_from_wishlist(pet_id):
    pet = Pet.query.get_or_404(pet_id)
    if pet in current_user.wishlist_pets:
        current_user.wishlist_pets.remove(pet)
        db.session.commit()
        flash("Pet removed from wishlist!", "warning")
    return redirect(url_for("wishlist"))

@app.route("/pet/<int:id>")
def pet_profile(id):
    pet = Pet.query.get_or_404(id)
    return render_template("pet_profile.html", pet=pet)

@app.route('/adopt/<int:id>', methods=['POST'])
@login_required
def adopt_pet(id):
    pet = Pet.query.get_or_404(id)

    if pet.status == "Available":
        pet.status = "Sold"  # Change status to Sold
        db.session.commit()
        flash(f"Thank you for adopting {pet.name}! ❤️", "success")
    else:
        flash("This pet is no longer available for adoption.", "danger")

    return redirect(url_for('pet_profile', id=pet.id))


@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")

        # Here, you can store the message in a database if needed

        return redirect(url_for("index"))  # Redirects user to home page

    return render_template("contact.html")

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

# admin work

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.role != 'admin':  # Restrict access
            flash("Access denied! Admins only.", "danger")
            return redirect(url_for('dashboard'))  # Redirect to dashboard
        return func(*args, **kwargs)
    return wrapper

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    return render_template("admin_dashboard.html")  # Create this template

@app.route("/manage_users")
@login_required
@admin_required
def manage_users():
    users = User.query.all()  # Fetch all users from the database
    return render_template("manage_users.html", users=users)

@app.route("/delete_user/<int:user_id>")
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        flash("You cannot delete yourself!", "danger")
        return redirect(url_for("manage_users"))

    db.session.delete(user)
    db.session.commit()
    flash("User deleted successfully!", "success")
    return redirect(url_for("manage_users"))

@app.route("/manage_pets")
@login_required
@admin_required
def manage_pets():
    pets = Pet.query.all()  # Fetch all pets from the database
    return render_template("manage_pets.html", pets=pets)

@app.route("/admin_delete_pet/<int:id>")
@login_required
@admin_required
def admin_delete_pet(id):
    pet = Pet.query.get_or_404(id)
    db.session.delete(pet)
    db.session.commit()
    flash("Pet deleted successfully!", "success")
    return redirect(url_for("manage_pets"))


if __name__ == "__main__":
    app.run(port=5000, debug=False)

