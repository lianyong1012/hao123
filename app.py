from flask import Flask, redirect, url_for, session, request, render_template, jsonify
from msal import ConfidentialClientApplication
import os
import json
import logging

app = Flask(__name__)
app.secret_key = os.urandom(24)

# 配置日志
logging.basicConfig(level=logging.DEBUG)

CLIENT_ID = "YOUR_CLIENT_ID"            # 替换为你的应用程序 ID
CLIENT_SECRET = "YOUR_CLIENT_SECRET"    # 替换为你的应用程序秘密
TENANT_ID = "YOUT_TENANT_ID"            # 替换为你的目录 (租户) ID
AUTHORITY = f"https://login.partner.microsoftonline.cn/YOUR_TENANT_ID"

REDIRECT_PATH = "/getAToken"
SCOPE = ["User.Read"]

DATA_FILE = 'data.json'

app.config["SESSION_TYPE"] = "filesystem"

aad_app = ConfidentialClientApplication(
    CLIENT_ID, authority=AUTHORITY,
    client_credential=CLIENT_SECRET,
)

def read_data():
    try:
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'w') as f:
                json.dump({"groups": [], "links": []}, f)
            return {"groups": [], "links": []}
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        app.logger.error(f"Error reading data file: {e}")
        return {"groups": [], "links": []}

def write_data(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        app.logger.error(f"Error writing to data file: {e}")

@app.route('/')
def index():
    if 'user' not in session:
        return render_template('index.html', user=session.get('user'))
    else:
        return redirect(url_for('links'))

@app.route('/login')
def login():
    auth_url = aad_app.get_authorization_request_url(SCOPE, redirect_uri=url_for('authorized', _external=True))
    return redirect(auth_url)

@app.route(REDIRECT_PATH)
def authorized():
    if 'code' not in request.args:
        return redirect(url_for('index', _external=True))
    code = request.args['code']
    result = aad_app.acquire_token_by_authorization_code(code, scopes=SCOPE, redirect_uri=url_for('authorized', _external=True))
    if 'error' in result:
        return f"Login failure: {result['error']}"
    session['user'] = result.get('id_token_claims')
    return redirect(url_for('index', _external=True))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index', _external=True))

@app.route('/links', methods=['GET', 'POST'])
def links():
    if 'user' not in session:
        return redirect(url_for('login', _external=True))

    data = read_data()

    if request.method == 'POST':
        if 'category' in request.form:
            new_link = {
                "name": request.form.get('name', ''),
                "url": request.form.get('url', ''),
                "category": request.form.get('category', '')
            }
            app.logger.debug(f"Adding new link: {new_link}")
            data['links'].append(new_link)
            write_data(data)
        elif 'new_category' in request.form:
            new_group = request.form.get('new_category', '')
            if new_group and new_group not in data['groups']:
                data['groups'].append(new_group)
                app.logger.debug(f"Adding new category: {new_group}")
                write_data(data)

    grouped_links = {}
    for link in data['links']:
        category = link.get('category', 'Uncategorized')
        if category not in grouped_links:
            grouped_links[category] = []
        grouped_links[category].append(link)

    return render_template('links.html', user=session.get('user'), groups=data['groups'], grouped_links=grouped_links)

@app.route('/edit_link', methods=['POST'])
def edit_link():
    if 'user' not in session:
        return redirect(url_for('login', _external=True))

    name = request.form.get('name')
    url = request.form.get('url')
    category = request.form.get('category')
    old_name = request.form.get('old_name')

    data = read_data()
    for link in data['links']:
        if link['name'] == old_name:
            link['name'] = name
            link['url'] = url
            link['category'] = category
            break
    write_data(data)
    return redirect(url_for('links'))

@app.route('/delete_link/<string:name>', methods=['POST'])
def delete_link(name):
    if 'user' not in session:
        return redirect(url_for('login', _external=True))

    data = read_data()
    data['links'] = [link for link in data['links'] if link['name'] != name]
    write_data(data)
    return redirect(url_for('links'))

@app.route('/delete_group', methods=['POST'])
def delete_group():
    if 'user' not in session:
        return redirect(url_for('login', _external=True))

    delete_category = request.form.get('delete_category')

    data = read_data()
    data['groups'] = [group for group in data['groups'] if group != delete_category]
    data['links'] = [link for link in data['links'] if link['category'] != delete_category]

    write_data(data)
    return redirect(url_for('links'))


if __name__ == "__main__":
    if not os.path.exists(DATA_FILE):
        write_data({"groups": [], "links": []})
    app.run(debug=True)
