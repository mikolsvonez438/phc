from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from supabase import create_client
import os
from datetime import datetime
from functools import wraps
import json
import requests

app = Flask(__name__, 
    static_folder='../static',
    template_folder='../templates'
)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'secretngaeh')  # Better security

# Supabase configuration
url = os.getenv('SUPABASE_URL', "https://btpdhndsiyodptyuodps.supabase.co")
key = os.getenv('SUPABASE_KEY', "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ0cGRobmRzaXlvZHB0eXVvZHBzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mzg4MDEwMjUsImV4cCI6MjA1NDM3NzAyNX0.i1NUi2DT4vnNcjbpmb_axBGeLupb97mntuF-ihdUcqs")
supabase = create_client(url, key)
DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'Freemium')

def get_client_ip():
    """Get client's IP address"""
    ip = requests.get('https://httpbin.org/ip')
    return ip.json()["origin"]
    

def get_user_agent():
    """Get client's user agent"""
    return request.headers.get('User-Agent')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_content/<int:giveaway_id>')
def create_content(giveaway_id):
    return render_template(
        'create_content.html', 
        giveaway_id=giveaway_id,
        default_admin_password=DEFAULT_ADMIN_PASSWORD
    )

@app.route('/view/<int:giveaway_id>')
def view_giveaway(giveaway_id):
    return render_template('view_giveaway.html', giveaway_id=giveaway_id)

@app.route('/admin/<int:giveaway_id>')
def admin_panel(giveaway_id):
    return render_template('admin_panel.html', giveaway_id=giveaway_id)

@app.route('/api/create_giveaway', methods=['POST'])
def create_giveaway():
    try:
        data = supabase.table('phc_giveaways').insert({
            "isLive": True
        }).execute()
        return jsonify({"success": True, "data": data.data[0]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/save_content', methods=['POST'])
def save_content():
    try:
        content = request.json.get('content')
        password = request.json.get('password')
        view_limit = request.json.get('viewLimit')
        giveaway_id = request.json.get('giveawayId')
        admin_password = request.json.get('adminPassword')  # New admin password for managing the giveaway

        data = supabase.table('phc_giveaway_contents').insert({
            "giveaway_id": giveaway_id,
            "content": content,
            "password": password,
            "admin_password": admin_password,
            "view_limit": view_limit,
            "current_views": 0
        }).execute()

        return jsonify({
            "success": True, 
            "data": data.data[0],
            "adminUrl": f"/admin/{giveaway_id}"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/view_content/<int:giveaway_id>', methods=['POST'])
def view_content(giveaway_id):
    try:
        password = request.json.get('password')
        ip_address = get_client_ip()
        user_agent = get_user_agent()

        # Check if this IP has already viewed the content
        existing_view = supabase.table('phc_giveaway_viewers')\
            .select("*")\
            .eq("giveaway_id", giveaway_id)\
            .eq("ip_address", ip_address)\
            .execute()

        if existing_view.data:
            # If already viewed, return content without incrementing view count
            content_data = supabase.table('phc_giveaway_contents')\
                .select("*")\
                .eq("giveaway_id", giveaway_id)\
                .execute()

            if not content_data.data:
                return jsonify({"success": False, "error": "Content not found"})

            content = content_data.data[0]
            
            if content['password'] != password:
                return jsonify({"success": False, "error": "Invalid password"})

            return jsonify({
                "success": True,
                "data": {
                    "content": content['content'],
                    "viewsLeft": content['view_limit'] - content['current_views'],
                    "alreadyViewed": True
                }
            })

        # Get content and check password
        content_data = supabase.table('phc_giveaway_contents')\
            .select("*")\
            .eq("giveaway_id", giveaway_id)\
            .execute()

        if not content_data.data:
            return jsonify({"success": False, "error": "Content not found"})

        content = content_data.data[0]

        if content['password'] != password:
            return jsonify({"success": False, "error": "Invalid password"})

        if content['current_views'] >= content['view_limit']:
            return jsonify({"success": False, "error": "View limit reached"})

        # Record the view
        supabase.table('phc_giveaway_viewers').insert({
            "giveaway_id": giveaway_id,
            "ip_address": ip_address,
            "user_agent": user_agent
        }).execute()

        # Increment view count
        supabase.table('phc_giveaway_contents')\
            .update({"current_views": content['current_views'] + 1})\
            .eq("giveaway_id", giveaway_id)\
            .execute()

        return jsonify({
            "success": True,
            "data": {
                "content": content['content'],
                "viewsLeft": content['view_limit'] - (content['current_views'] + 1),
                "alreadyViewed": False
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/admin/stats/<int:giveaway_id>', methods=['POST'])
def get_admin_stats(giveaway_id):
    try:
        admin_password = request.json.get('adminPassword')

        # Verify admin password
        content_data = supabase.table('phc_giveaway_contents')\
            .select("*")\
            .eq("giveaway_id", giveaway_id)\
            .execute()

        if not content_data.data or content_data.data[0]['admin_password'] != admin_password:
            return jsonify({"success": False, "error": "Invalid admin password"})

        # Get viewers data
        viewers_data = supabase.table('phc_giveaway_viewers')\
            .select("*")\
            .eq("giveaway_id", giveaway_id)\
            .execute()

        return jsonify({
            "success": True,
            "data": {
                "content": content_data.data[0],
                "viewers": viewers_data.data,
                "totalViews": len(viewers_data.data),
                "viewsLeft": content_data.data[0]['view_limit'] - content_data.data[0]['current_views']
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

