from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify
import sqlite3
import os
from werkzeug.utils import secure_filename

# initializations
app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

UPLOAD_FOLDER = 'static/proofs/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('users.db')
        g.db.row_factory = sqlite3.Row
    return g.db

@app.before_request
def before_request():
    g.db = get_db()

@app.teardown_request
def teardown_request(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# homepage route
@app.route('/')
def index():
    # check if user is logged in
    if 'user_id' in session:
        user_id = session['user_id']

        db = get_db()
        cursor = db.cursor()
        
        # query for the points field
        cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
        user = cursor.fetchone()

        # For current challenges
        cursor.execute("SELECT * FROM challenges WHERE status = 'active' AND (user1_id = ? OR user2_id = ?)", (user_id, user_id))
        current_challenges = cursor.fetchall()

        # For available challenges
        cursor.execute("""
        SELECT * FROM challenges 
        WHERE status = 'active' AND id NOT IN (
            SELECT id FROM challenges 
            WHERE user1_id = ? OR user2_id = ?
        )
        """, (user_id, user_id))
        available_challenges = cursor.fetchall()

        # render the homepage with username, points, and challenges
        action = request.args.get('action', '') or None
        return render_template('index.html', user=user, current_challenges=current_challenges, available_challenges=available_challenges, action=action)
    
    return redirect(url_for('login'))

# login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # check login credentials
        username = request.form.get('username')
        password = request.form.get('password')
        
        db = get_db()
        cursor = db.cursor()

        # select user from users table
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        
        # check if user exists
        if user:
            # set session variables
            session['user_id'] = user['id']
            return redirect(url_for('index',  action='loginSuccess'))
        else:
            # invalid credentials, show error message
            error = 'Invalid username or password'
            return render_template('login.html', error=error)
    if request.method == "GET":
        return render_template('login.html')

# signup route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # get form data
        username = request.form.get('username')
        password = request.form.get('password')
        
        db = get_db()
        cursor = db.cursor()

        # check if username is already taken
        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            error = 'Username already taken'
            return render_template('signup.html', error=error)
        else:
            # create new user account
            cursor.execute("INSERT INTO users (username, password, points, trees_planted, challenge_completed) VALUES (?, ?, 0, 0, 0)", (username, password))
            db.commit()
            
            # logs user in
            session['user_id'] = cursor.lastrowid
            
            return redirect(url_for('index', action='signupSuccess'))
    
    return render_template('signup.html')

# logout route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


# create a new challenge
@app.route('/create_challenge', methods=['GET', 'POST'])
def create_challenge():

    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        # get form data
        title = request.form.get('challenge-title')
        activity = request.form.get('activity')
        time = request.form.get('challenge-date')
        points = request.form.get('points-wagered')
        status = 'active'
        
        # create new challenge
        cursor.execute("INSERT INTO challenges (name, activity, duration, points, status) VALUES (?, ?, ?, ?, ?)", (title, activity, time, points, status))
        db.commit()
        
        return redirect(url_for('index', action='challengeCreated'))
    

    cursor.execute("SELECT * FROM users WHERE id=?", (session['user_id'],))
    user = cursor.fetchone()
    
    return render_template('create_challenge.html', user=user)


@app.route('/join/<int:challenge_id>')
def join(challenge_id):
    user_id = session['user_id']
    
    db = get_db()
    cursor = db.cursor()

    # check if the current user is already part of the challenge
    cursor.execute("SELECT * FROM challenges WHERE id=? AND (user1_id=? OR user2_id=?)", (challenge_id, user_id, user_id))
    if cursor.fetchone():
        # user is already in challenge
        return redirect(url_for('index'))
    
    # Determine whether to add user as user1 or user2
    cursor.execute("SELECT * FROM challenges WHERE id=?", (challenge_id,))
    challenge = cursor.fetchone()
    if not challenge['user1_id']:
        cursor.execute("UPDATE challenges SET user1_id=?, status='active' WHERE id=?", (user_id, challenge_id))
    elif not challenge['user2_id']:
        cursor.execute("UPDATE challenges SET user2_id=?, status='active' WHERE id=?", (user_id, challenge_id))
    else:
        # challenge is already full
        return redirect(url_for('index'))
    
    db.commit()
    return redirect(url_for('index', action='challengeJoined'))


@app.route('/open/<int:challenge_id>')
def open_challenge(challenge_id):
    user_id = session.get('user_id')
    if not user_id:
        # Redirect to login if user is not logged in or handle accordingly
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()

    # Query for the challenge with the given challenge_id
    cursor.execute("""
        SELECT *, 
        (user1_id = ?) AS is_user1, 
        (user2_id = ?) AS is_user2 
        FROM challenges WHERE id=?""", (user_id, user_id, challenge_id,))
    challenge = cursor.fetchone()

    if not challenge:
        # Handle case where challenge doesn't exist
        return "Challenge not found", 404

    # Determine the proof URLs for the current user and the other user
    current_user_proof = None
    other_user_proof = None
    if challenge['is_user1']:
        current_user_proof = challenge['proof_url_user1']
        other_user_proof = challenge['proof_url_user2']
    elif challenge['is_user2']:
        current_user_proof = challenge['proof_url_user2']
        other_user_proof = challenge['proof_url_user1']

    # Query for the current user and other user from the users table
    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    current_user = cursor.fetchone()

    other_user_id = challenge['user1_id'] if challenge['is_user2'] else challenge['user2_id']
    cursor.execute("SELECT * FROM users WHERE id=?", (other_user_id,))
    other_user = cursor.fetchone()

    # Render the challenge page with the challenge details, proof URLs, current user, and other user
    return render_template('challenge_page.html', 
                           challenge=challenge, 
                           current_user_proof=current_user_proof, 
                           other_user_proof=other_user_proof,
                           current_user=current_user,
                           other_user=other_user)

@app.route('/give_up/<int:challenge_id>')
def give_up(challenge_id):
    user_id = session['user_id']
    
    db = get_db()
    cursor = db.cursor()

    # Check if the current user is user1 or user2 in the challenge
    cursor.execute("SELECT user1_id, user2_id FROM challenges WHERE id=?", (challenge_id,))
    challenge = cursor.fetchone()

    if not challenge:
        return "Challenge not found", 404

    # Determine if the current user is user1 or user2, and update the challenge accordingly
    if challenge['user1_id'] == user_id:
        # Remove user1 from challenge and clear user1's proof
        cursor.execute("UPDATE challenges SET user1_id=NULL, proof_url_user1=NULL, status='active' WHERE id=?", (challenge_id,))
    elif challenge['user2_id'] == user_id:
        # Remove user2 from challenge and clear user2's proof
        cursor.execute("UPDATE challenges SET user2_id=NULL, proof_url_user2=NULL, status='active' WHERE id=?", (challenge_id,))
    
    db.commit()
    
    return redirect(url_for('index', action='challengeGivenUp'))


@app.route('/complete_challenge/<int:challenge_id>')
def complete_challenge(challenge_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()

    # Fetch the challenge details including user IDs and points
    cursor.execute("""
        SELECT * FROM challenges 
        WHERE id=? AND status='active' AND (user1_id=? OR user2_id=?)
    """, (challenge_id, user_id, user_id))
    challenge = cursor.fetchone()

    if not challenge:
        return "Challenge not found or already completed", 404

    # Determine the state of the challenge (which users have uploaded proofs)
    user1_proof = challenge['proof_url_user1']
    user2_proof = challenge['proof_url_user2']
    points = challenge['points']

    update_points_sql = "UPDATE users SET points = points + ?, challenge_completed = challenge_completed + 1 WHERE id = ?"
    deduct_points_sql = "UPDATE users SET points = points - ? WHERE id = ?"
    action = ''

    if user1_proof and not user2_proof:
        # User 1 wins, User 2 loses
        cursor.execute(update_points_sql, (points, challenge['user1_id']))
        cursor.execute(deduct_points_sql, (points, challenge['user2_id']))
        action = 'challengeSuccess'
    elif user2_proof and not user1_proof:
        # User 2 wins, User 1 loses
        cursor.execute(update_points_sql, (points, challenge['user2_id']))
        cursor.execute(deduct_points_sql, (points, challenge['user1_id']))
        action = 'challengeFailure'
    elif user1_proof and user2_proof:
        # Both users win, no points are deducted
        cursor.execute(update_points_sql, (points, challenge['user1_id']))
        cursor.execute(update_points_sql, (points, challenge['user2_id']))
        action = 'mutualWin'
    # If neither user wins, no points are updated
        
    # Update challenge status to 'completed'
    cursor.execute("UPDATE challenges SET status='completed' WHERE id=?", (challenge_id,))
    db.commit()

    return redirect(url_for('index', action='challengeCompleted'))


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400
    file = request.files['file']
    user_id = request.form.get('user_id', type=int)
    challenge_id = request.form.get('challenge_id', type=int)
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    if not allowed_file(file.filename):
        return jsonify({'message': 'Invalid file type'}), 400

    if file and allowed_file(file.filename):
        # Generate a unique filename using user_id and challenge_id
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = secure_filename(f"{user_id}_{challenge_id}.{ext}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)

        # Determine if the user is user1 or user2 in the challenge
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT user1_id, user2_id FROM challenges WHERE id=?", (challenge_id,))
        row = cursor.fetchone()
        
        if row:
            if user_id == row['user1_id']:
                proof_field = 'proof_url_user1'
            elif user_id == row['user2_id']:
                proof_field = 'proof_url_user2'
            else:
                return jsonify({'message': 'User is not a participant in this challenge'}), 400

            # Update database with file_path for the correct user
            cursor.execute(f"UPDATE challenges SET {proof_field}=? WHERE id=?", (file_path, challenge_id))
            db.commit()
            return jsonify({'message': 'File successfully uploaded', 'file_path': file_path})
        else:
            return jsonify({'message': 'Challenge not found'}), 404

@app.route('/profile')
def profile():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        return redirect(url_for('login'))

    return render_template('profile.html', user=user)

@app.route('/leaderboard')
def leaderboard():
    db = get_db()
    cursor = db.cursor()

    # Query the users table and order by the number of challenges won in descending order
    cursor.execute("""
        SELECT * FROM users 
        ORDER BY challenge_completed DESC
    """)
    users = cursor.fetchall()

    user_id = session['user_id']
    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    return render_template('leaderboard.html', username=user['username'], users=users)

@app.route('/shop')
def shop():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    return render_template('shop.html', user=user)

if __name__ == '__main__':
    app.run(debug=True)




