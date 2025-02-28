from flask import Flask, request, jsonify, redirect, render_template
from discord.ui import View, Button
from discord import app_commands
from discord.ext import commands
from random import randint
import threading
import requests
import discord
import json
import time
import os


from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BOT_TOKEN_1 = os.getenv("BOT_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
JSON_BIN_API_KEY = os.getenv("JSON_BIN_API")
REDIRECT_URI = os.getenv("SITE_URL")+"/callback"
BIN_ID = os.getenv("JSON_BIN_ID")


TOKEN_URL = "https://discord.com/api/oauth2/token"
USER_URL = "https://discord.com/api/users/@me"

#-------------------------------Inactivity-Management-----------------------------------#
# URL to send requests to
# Function to send the request
def send_request():
    try:
        response = requests.get(REDIRECT_URI)
        print(randint(10000,99999),"Response Code:", response.status_code)
    except Exception as e:
        print(f"An error occurred: {e}")

# Loop to send request every few seconds
def keep_active():
    while True:
        send_request()
        time.sleep(randint(0,20))
#---------------------------------------------------------------------------------------#

# Function to load verified users from JSONBin
def load_verified_users():
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}/latest"
    
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json().get("record", {})
    except (requests.RequestException, ValueError):
        data = {"servers": {}}  # Default structure if fetch fails

    # Ensure correct structure
    for server_id in data.get("servers", {}):
        if "verified_users" not in data["servers"][server_id]:
            data["servers"][server_id]["verified_users"] = []
        if "tokens" not in data["servers"][server_id]:
            data["servers"][server_id]["tokens"] = {}

    return data

# Function to save verified users to JSONBin
def save_verified_users(data):
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}"
    
    try:
        response = requests.put(url, json=data, headers=HEADERS)
        response.raise_for_status()
        print("✅ JSON updated successfully!")
    except requests.RequestException as e:
        print("❌ Error updating JSON:", e)



#------------------------------Flask-Implementation-------------------------------------------#

HEADERS = {
    "X-Master-Key": JSON_BIN_API_KEY,
    "Content-Type": "application/json"
}

app = Flask(__name__)
# OAuth2 Callback Route
@app.route("/callback")
def callback():
    code = request.args.get("code")
    server_id = request.args.get("state")  # Server ID passed in OAuth link

    if not code or not server_id:
        return render_template("error.html", message="Error: Missing code or server ID"), 400

    # Exchange code for access token
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    
    if response.status_code != 200:
        return render_template("error.html", message=f"Error fetching token: {response.json()}"), 400

    token_data = response.json()
    access_token = token_data["access_token"]

    # Get user information
    user_headers = {"Authorization": f"Bearer {access_token}"}
    user_response = requests.get(USER_URL, headers=user_headers)

    if user_response.status_code != 200:
        return render_template("error.html", message="Error fetching user info"), 400

    user_data = user_response.json()
    user_id = str(user_data["id"])  # Get the user ID

    # Save user and token
    data = load_verified_users()

    if server_id not in data["servers"]:
        data["servers"][server_id] = {"verified_users": [], "tokens": {}}

    if user_id not in data["servers"][server_id]["verified_users"]:
        data["servers"][server_id]["verified_users"].append(user_id)

    data["servers"][server_id]["tokens"][user_id] = access_token  # ✅ Store token properly

    save_verified_users(data)

    print(f"✅ Verified {user_id} in server {server_id} and stored token.")
    
    #payment block
    #bot1.loop.create_task(assign_verified_role(server_id, user_id))


    return render_template("callback.html", user_id=user_id, server_id=server_id)

# Run Flask app
def run_flask():
    port = int(os.environ.get("PORT",4000))
    app.run(host="0.0.0.0",port=port)

#---------------------------------------------------------------------------------------#


def add_user_to_guild(user_id, access_token, server_id):
    url = f"https://discord.com/api/guilds/{server_id}/members/{user_id}"
    headers = {
        "Authorization": f"Bot {BOT_TOKEN_1}",
        "Content-Type": "application/json"
    }
    data = {"access_token": access_token}

    response = requests.put(url, json=data, headers=headers)

    try:
        response_json = response.json()
    except requests.exceptions.JSONDecodeError:
        return f"Failed to add {user_id}: Empty response from Discord"

    if response.status_code == 201:
        return f"✅ Successfully added {user_id} to the server!"
    elif response.status_code == 204:
        return f"⚠️ {user_id} was already in the server."
    else:
        return f"❌ Failed to add {user_id}: {response_json}"



intents1 = discord.Intents.default()
intents1.members = True  # Allows fetching users
intents1.guilds = True    # Required for server-related actions

bot1 = commands.Bot(command_prefix="/", intents=intents1)
tree_bot_1 = bot1.tree  # For application commands

async def assign_verified_role(server_id, user_id):
    guild = bot1.get_guild(int(server_id))  # Fetch the guild (server)
    if not guild:
        print(f"❌ Guild {server_id} not found!")
        return
    
    member = guild.get_member(int(user_id))  # Fetch the user in the server
    if not member:
        print(f"❌ User {user_id} not found in guild {server_id}!")
        return

    role_name = "member"
    role = discord.utils.get(guild.roles, name=role_name)

    # If role doesn't exist, create it
    if role is None:
        role = await guild.create_role(name=role_name, colour=discord.Colour.blue())

    # Assign the role
    await member.add_roles(role)
    print(f"✅ Assigned role '{role.name}' to {member.display_name}!")


@tree_bot_1.command(name="verify", description="Sends the verification link.")
async def verify(interaction: discord.Interaction):
    server_id = str(interaction.guild.id)
    auth_url = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&response_type=code&scope=identify%20guilds.join&redirect_uri={REDIRECT_URI}&state={server_id}"

    # Create a button
    class VerifyButton(View):
        def __init__(self):
            super().__init__()
            self.add_item(Button(label="Verify Here", url=auth_url, style=discord.ButtonStyle.link))

    # Send the button as a response
    await interaction.response.send_message("Click the button below to verify:", view=VerifyButton(), ephemeral=True)

@tree_bot_1.command(name="join", description="Adds all verified users of this server to another server.")
async def join(interaction: discord.Interaction, server_id: str):
    server_owner_id = interaction.guild.owner_id  # Get owner ID of the current server
    user_id = interaction.user.id  # The ID of the user who ran the command

    # Only allow the owner to run this command
    if user_id != server_owner_id:
        await interaction.response.send_message("❌ Only the server owner can use this command!", ephemeral=True)
        return

    # Load verified users
    data = load_verified_users()
    current_server_id = str(interaction.guild.id)

    # Check if there are verified users in the current server
    if current_server_id not in data["servers"] or not data["servers"][current_server_id]["verified_users"]:
        await interaction.response.send_message("⚠️ No verified users found in this server!", ephemeral=True)
        return

    verified_users = data["servers"][current_server_id]["verified_users"]
    tokens = data["servers"][current_server_id]["tokens"]

    # Track results
    results = []

    for user_id in verified_users:
        access_token = tokens.get(user_id)
        if not access_token:
            results.append(f"⚠️ No token for <@{user_id}>. They need to verify again.")
            continue

        # Try to add user
        result = add_user_to_guild(user_id, access_token, server_id)
        results.append(result)

    # Send summary message
    await interaction.response.send_message("\n".join(results), ephemeral=True)

@tree_bot_1.command(name="about", description="Displays bot info.")
async def about(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Bot Information",
        description="This bot verifies users and allows them to join servers securely!",
        color=discord.Color.blue()
    )

    embed.add_field(name="🛠 Commands", value=(
        "**`/verify`** - Sends the verification link.\n"
        "**`/join [server_id]`** - Adds verified users to another server.\n"
        "**`/list`** - Lists all verified users in the server.\n"
        "**`/about`** - Shows information about the bot."
    ), inline=False)

    embed.set_footer(text="Made for secure user verification and seamless server joining.")

    await interaction.response.send_message(embed=embed)


@tree_bot_1.command(name="list", description="Lists verified users in the current server.")
async def list_users(interaction: discord.Interaction):
    server_id = str(interaction.guild.id)
    data = load_verified_users()

    if server_id in data["servers"] and data["servers"][server_id]["verified_users"]:
        verified_users = data["servers"][server_id]["verified_users"]
        user_list = "\n".join([f"- <@{uid}> (`{uid}`)" for uid in verified_users])

        embed = discord.Embed(
            title="✅ Verified Users",
            description=user_list,
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Total: {len(verified_users)} users")

        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="⚠️ No Verified Users",
            description="There are no verified users in this server.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)



@bot1.event
async def on_ready():
    await tree_bot_1.sync()
    print(f"✅ Logged in as {bot1.user}")

def run_bot_1():
    bot1.run(BOT_TOKEN_1)

flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

activity_thread = threading.Thread(target=keep_active, daemon=True)
activity_thread.start()

#bot1_thread = threading.Thread(target=run_bot_1, daemon=True)
#bot1_thread.start()

run_bot_1()
