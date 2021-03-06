from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker, scoped_session
from database_setup import Base, User, Categories, Items

# New imports for this step
from flask import session as login_session
import random
import string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
# helpers


def create_user(login_session):
    nuser = User(name=login_session['username'], email=login_session[
        'email'])
    session.add(nuser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def get_user_info(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def get_user_id(u_email):
    try:
        user = session.query(User).filter_by(email=u_email).one()
        return user.id
    except:
        return None


CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = 'item catalog'
app = Flask(__name__)
engine = create_engine('sqlite:///itemcat.db')
Base.metadata.bind = engine

session = scoped_session(sessionmaker(bind=engine))


@app.route('/login')
def login_s():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    u_id = get_user_id(login_session['email'])

    if not u_id:
        u_id = create_user(login_session)
    login_session['user_id'] = u_id

    return "done"+login_session['username']


@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user.
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] == '200':
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        response = make_response(json.dumps(
            'Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


@app.route('/')
@app.route('/categories')
def main_page():
    categories = session.query(Categories)
    return render_template('index.html', cat=categories)

@app.route('/logout')
def logout():
    if 'username' in login_session:
        gdisconnect()
        del login_session['gplus_id']
        del login_session['access_token']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        return redirect(url_for("main_page"))
    else:
        return redirect(url_for("login_s"))

@app.route('/categories/<catname>')
def show_cat_items(catname):
    get_cat = session.query(Categories).filter_by(name=catname).one()
    cat_items = session.query(Items).filter_by(c_id=get_cat.id).all()
    return render_template('show_cat.html', cat=get_cat, cat_items=cat_items)


@app.route('/categories/<catname>/<int:item_id>')
def show_item(catname, item_id):
    get_cat = session.query(Categories).filter_by(name=catname).one()
    item = session.query(Items).filter_by(id=item_id, c_id=get_cat.id).one()
    return render_template('show_item.html', item=item, cat=catname)


@app.route('/categories/new', methods=['GET', 'POST'])
def add_cat():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        new_cat = Categories(
            name=request.form['name'], u_id=login_session['user_id'])
        session.add(new_cat)
        session.commit()
        return redirect(url_for('main_page'))
    else:
        return render_template("new_cat.html")


@app.route('/categories/<catname>/new', methods=['GET', 'POST'])
def add_item(catname):
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        get_cat = session.query(Categories).filter_by(name=catname).one()
        new_item = Items(name=request.form['name'], c_id=get_cat.id,
                         u_id=login_session['user_id'],
                         description=request.form['desc'])
        session.add(new_item)
        session.commit()
        return redirect(url_for('show_cat_items', catname=catname))
    else:
        return render_template('add_new_item.html', cname=catname)


@app.route('/categories/<catname>/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_item(catname, item_id):
    if 'username' not in login_session:
        return redirect('/login')
    edited_item = session.query(Items).filter_by(id=item_id).one()
    #get_cat = session.query(Categories).filter_by(name=catname).one()
    if login_session['user_id'] != edited_item.u_id:
        return ("""<script>function myFunction() {alert('You are not authorized to edit this restaurant.
                  Please create your own restaurant in order to edit.');}
                  </script>
                  <body onload='myFunction()'>""")
    if request.method == 'POST':
        edited_item.name = request.form['name']
        edited_item.description = request.form['desc']
        session.add(edited_item)
        session.commit()
        return redirect(url_for('show_item', catname=catname, item_id=item_id))
    else:
        return render_template('edit_item.html', item=edited_item, cat=catname)


@app.route('/categories/<catname>/<int:item_id>/delete', methods=['GET', 'POST'])
def delete_item(catname, item_id):
    if 'username' not in login_session:
        return redirect('/login')
    deleted_item = session.query(Items).filter_by(id=item_id).one()
    #get_cat = session.query(Categories).filter_by(name=catname).one()
    if login_session['user_id'] != deleted_item.u_id:
        return ("""<script>function myFunction() {alert('You are not authorized to edit this restaurant.
                  Please create your own restaurant in order to edit.');}
                  </script>
                  <body onload='myFunction()'>""")
    if request.method == 'POST':
        session.delete(deleted_item)
        session.commit()
        return redirect(url_for("show_cat_items", catname=catname))
    else:
        return render_template("delete_item.html", cat=catname, item=deleted_item)

app.secret_key = 'super_secret_key'
if __name__ == '__main__':
    app.config['SESSION_TYPE'] = 'filesystem'
    app.debug = True
    app.run(host="0.0.0.0", port=5000)
