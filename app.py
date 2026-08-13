import os
import time
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from requests_oauthlib import OAuth1Session

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default-dev-key')

API_KEY = os.getenv('FLICKR_API_KEY')
API_SECRET = os.getenv('FLICKR_API_SECRET')

REQUEST_TOKEN_URL = 'https://www.flickr.com/services/oauth/request_token'
AUTHORIZE_URL = 'https://www.flickr.com/services/oauth/authorize'
ACCESS_TOKEN_URL = 'https://www.flickr.com/services/oauth/access_token'
REST_API_URL = 'https://www.flickr.com/services/rest/'


def get_oauth_session():
  return OAuth1Session(
      API_KEY,
      client_secret=API_SECRET,
      resource_owner_key=session.get('access_token'),
      resource_owner_secret=session.get('access_token_secret'),
  )


@app.route('/')
def index():
  return render_template(
      'index.html', authenticated=('access_token' in session)
  )


@app.route('/auth')
def auth():
  oauth = OAuth1Session(
      API_KEY,
      client_secret=API_SECRET,
      callback_uri=url_for('auth_callback', _external=True),
  )
  fetch_response = oauth.fetch_request_token(REQUEST_TOKEN_URL)

  session['req_token'] = fetch_response.get('oauth_token')
  session['req_token_secret'] = fetch_response.get('oauth_token_secret')

  authorization_url = oauth.authorization_url(AUTHORIZE_URL, perms='write')
  return redirect(authorization_url)


@app.route('/auth/callback')
def auth_callback():
  req_token = session.get('req_token')
  req_token_secret = session.get('req_token_secret')
  verifier = request.args.get('oauth_verifier')

  oauth = OAuth1Session(
      API_KEY,
      client_secret=API_SECRET,
      resource_owner_key=req_token,
      resource_owner_secret=req_token_secret,
      verifier=verifier,
  )

  oauth_tokens = oauth.fetch_access_token(ACCESS_TOKEN_URL)

  session['access_token'] = oauth_tokens.get('oauth_token')
  session['access_token_secret'] = oauth_tokens.get('oauth_token_secret')
  session['user_nsid'] = oauth_tokens.get('user_nsid')

  session.pop('req_token', None)
  session.pop('req_token_secret', None)

  return redirect(url_for('index'))


@app.route('/logout')
def logout():
  session.clear()
  return redirect(url_for('index'))


@app.route('/api/photos', methods=['GET'])
def get_photos():
  if 'access_token' not in session:
    return jsonify({'error': 'Not authenticated'}), 401

  oauth = get_oauth_session()
  page = request.args.get('page', 1, type=int)
  per_page = request.args.get('per_page', 24, type=int)
  sort_dir = request.args.get('sort', 'date-posted-desc')

  params = {
      'method': 'flickr.photos.search',
      'user_id': session['user_nsid'],
      'per_page': per_page,
      'page': page,
      'sort': sort_dir,
      'extras': 'description,tags,date_taken,geo,o_dims,url_s,url_m',
      'format': 'json',
      'nojsoncallback': 1,
  }

  res = oauth.get(REST_API_URL, params=params)
  return jsonify(res.json().get('photos', {}))


@app.route('/api/photo-details', methods=['GET'])
def get_photo_details():
  if 'access_token' not in session:
    return jsonify({'error': 'Not authenticated'}), 401

  photo_id = request.args.get('photo_id')
  if not photo_id:
    return jsonify({'error': 'Missing photo ID'}), 400

  oauth = get_oauth_session()
  res = oauth.get(
      REST_API_URL,
      params={
          'method': 'flickr.photos.getInfo',
          'photo_id': photo_id,
          'format': 'json',
          'nojsoncallback': 1,
      },
  ).json()

  return jsonify(res.get('photo', {}))


@app.route('/api/bulk-update', methods=['POST'])
def bulk_update():
  if 'access_token' not in session:
    return jsonify({'error': 'Not authenticated'}), 401

  data = request.json or {}
  photo_ids = data.get('photo_ids', [])
  tags_to_add = data.get('add_tags', '').strip()
  title_prefix = data.get('title_prefix', '').strip()
  append_desc = data.get('append_description', '').strip()

  oauth = get_oauth_session()
  results = {'success': [], 'failed': [], 'snapshots': []}

  for pid in photo_ids:
    try:
      info_res = oauth.get(
          REST_API_URL,
          params={
              'method': 'flickr.photos.getInfo',
              'photo_id': pid,
              'format': 'json',
              'nojsoncallback': 1,
          },
      ).json()
      photo_info = info_res.get('photo', {})

      curr_title = photo_info.get('title', {}).get('_content', '')
      curr_desc = photo_info.get('description', {}).get('_content', '')
      curr_tags = [
          t.get('raw', t.get('_content'))
          for t in photo_info.get('tags', {}).get('tag', [])
      ]

      # Save pre-change snapshot for undo
      results['snapshots'].append({
          'photo_id': pid,
          'title': curr_title,
          'description': curr_desc,
          'tags': curr_tags,
      })

      if tags_to_add:
        oauth.post(
            REST_API_URL,
            data={
                'method': 'flickr.photos.addTags',
                'photo_id': pid,
                'tags': tags_to_add,
                'format': 'json',
                'nojsoncallback': 1,
            },
        )

      if title_prefix or append_desc:
        new_title = (
            f'{title_prefix} {curr_title}'.strip()
            if title_prefix
            else curr_title
        )
        new_desc = (
            f'{curr_desc}\n{append_desc}'.strip() if append_desc else curr_desc
        )

        oauth.post(
            REST_API_URL,
            data={
                'method': 'flickr.photos.setMeta',
                'photo_id': pid,
                'title': new_title,
                'description': new_desc,
                'format': 'json',
                'nojsoncallback': 1,
            },
        )

      results['success'].append(pid)
      time.sleep(0.15)
    except Exception as err:
      results['failed'].append({'id': pid, 'error': str(err)})

  return jsonify(results)


@app.route('/api/replace-tags', methods=['POST'])
def replace_tags():
  if 'access_token' not in session:
    return jsonify({'error': 'Not authenticated'}), 401

  data = request.json or {}
  photo_ids = data.get('photo_ids', [])
  find_tag = data.get('find_tag', '').strip().lower()
  replace_tag = data.get('replace_tag', '').strip()

  if not photo_ids or not find_tag:
    return jsonify({'error': 'Missing photo IDs or find tag'}), 400

  oauth = get_oauth_session()
  results = {'success': [], 'failed': [], 'snapshots': []}

  for pid in photo_ids:
    try:
      info_res = oauth.get(
          REST_API_URL,
          params={
              'method': 'flickr.photos.getInfo',
              'photo_id': pid,
              'format': 'json',
              'nojsoncallback': 1,
          },
      ).json()
      photo_info = info_res.get('photo', {})
      existing_tags = [
          t.get('raw', t.get('_content'))
          for t in photo_info.get('tags', {}).get('tag', [])
      ]

      results['snapshots'].append({
          'photo_id': pid,
          'tags': existing_tags,
      })

      new_tag_list = []
      modified = False
      for t in existing_tags:
        if t.lower() == find_tag:
          modified = True
          if replace_tag:
            new_tag_list.append(
                f'"{replace_tag}"' if ' ' in replace_tag else replace_tag
            )
        else:
          new_tag_list.append(f'"{t}"' if ' ' in t else t)

      if modified:
        tags_str = ' '.join(new_tag_list)
        oauth.post(
            REST_API_URL,
            data={
                'method': 'flickr.photos.setTags',
                'photo_id': pid,
                'tags': tags_str,
                'format': 'json',
                'nojsoncallback': 1,
            },
        )

      results['success'].append(pid)
      time.sleep(0.15)
    except Exception as err:
      results['failed'].append({'id': pid, 'error': str(err)})

  return jsonify(results)


@app.route('/api/bulk-dates', methods=['POST'])
def bulk_dates():
  if 'access_token' not in session:
    return jsonify({'error': 'Not authenticated'}), 401

  data = request.json or {}
  photo_ids = data.get('photo_ids', [])
  date_taken = data.get('date_taken', '').strip()

  if not photo_ids or not date_taken:
    return jsonify({'error': 'Missing photo IDs or date'}), 400

  oauth = get_oauth_session()
  results = {'success': [], 'failed': [], 'snapshots': []}

  for pid in photo_ids:
    try:
      info_res = oauth.get(
          REST_API_URL,
          params={
              'method': 'flickr.photos.getInfo',
              'photo_id': pid,
              'format': 'json',
              'nojsoncallback': 1,
          },
      ).json()
      curr_date = (
          info_res.get('photo', {}).get('dates', {}).get('taken', '')
      )

      results['snapshots'].append({
          'photo_id': pid,
          'date_taken': curr_date,
      })

      oauth.post(
          REST_API_URL,
          data={
              'method': 'flickr.photos.setDates',
              'photo_id': pid,
              'date_taken': date_taken,
              'format': 'json',
              'nojsoncallback': 1,
          },
      )
      results['success'].append(pid)
      time.sleep(0.15)
    except Exception as err:
      results['failed'].append({'id': pid, 'error': str(err)})

  return jsonify(results)


@app.route('/api/bulk-geo', methods=['POST'])
def bulk_geo():
  if 'access_token' not in session:
    return jsonify({'error': 'Not authenticated'}), 401

  data = request.json or {}
  photo_ids = data.get('photo_ids', [])
  lat = data.get('lat')
  lon = data.get('lon')

  if not photo_ids or lat is None or lon is None:
    return jsonify({'error': 'Missing photo IDs or coordinates'}), 400

  oauth = get_oauth_session()
  results = {'success': [], 'failed': [], 'snapshots': []}

  for pid in photo_ids:
    try:
      info_res = oauth.get(
          REST_API_URL,
          params={
              'method': 'flickr.photos.getInfo',
              'photo_id': pid,
              'format': 'json',
              'nojsoncallback': 1,
          },
      ).json()
      loc = info_res.get('photo', {}).get('location', {})

      results['snapshots'].append({
          'photo_id': pid,
          'lat': loc.get('latitude'),
          'lon': loc.get('longitude'),
      })

      oauth.post(
          REST_API_URL,
          data={
              'method': 'flickr.photos.geo.setLocation',
              'photo_id': pid,
              'lat': lat,
              'lon': lon,
              'format': 'json',
              'nojsoncallback': 1,
          },
      )
      results['success'].append(pid)
      time.sleep(0.15)
    except Exception as err:
      results['failed'].append({'id': pid, 'error': str(err)})

  return jsonify(results)


@app.route('/api/undo', methods=['POST'])
def undo_action():
  """Restores metadata based on a snapshot payload passed from client history."""
  if 'access_token' not in session:
    return jsonify({'error': 'Not authenticated'}), 401

  snapshots = request.json.get('snapshots', [])
  if not snapshots:
    return jsonify({'error': 'No snapshot data found'}), 400

  oauth = get_oauth_session()
  results = {'success': [], 'failed': []}

  for snap in snapshots:
    pid = snap.get('photo_id')
    try:
      # Restore Title & Description if present in snapshot
      if 'title' in snap or 'description' in snap:
        oauth.post(
            REST_API_URL,
            data={
                'method': 'flickr.photos.setMeta',
                'photo_id': pid,
                'title': snap.get('title', ''),
                'description': snap.get('description', ''),
                'format': 'json',
                'nojsoncallback': 1,
            },
        )

      # Restore Tags if present
      if 'tags' in snap:
        tags_str = ' '.join(
            [f'"{t}"' if ' ' in t else t for t in snap['tags']]
        )
        oauth.post(
            REST_API_URL,
            data={
                'method': 'flickr.photos.setTags',
                'photo_id': pid,
                'tags': tags_str,
                'format': 'json',
                'nojsoncallback': 1,
            },
        )

      # Restore Date Taken if present
      if 'date_taken' in snap and snap['date_taken']:
        oauth.post(
            REST_API_URL,
            data={
                'method': 'flickr.photos.setDates',
                'photo_id': pid,
                'date_taken': snap['date_taken'],
                'format': 'json',
                'nojsoncallback': 1,
            },
        )

      # Restore Geo Location if present
      if 'lat' in snap and 'lon' in snap and snap['lat'] is not None:
        oauth.post(
            REST_API_URL,
            data={
                'method': 'flickr.photos.geo.setLocation',
                'photo_id': pid,
                'lat': snap['lat'],
                'lon': snap['lon'],
                'format': 'json',
                'nojsoncallback': 1,
            },
        )

      results['success'].append(pid)
      time.sleep(0.15)
    except Exception as err:
      results['failed'].append({'id': pid, 'error': str(err)})

  return jsonify(results)


if __name__ == '__main__':
  app.run(port=5000, debug=True)