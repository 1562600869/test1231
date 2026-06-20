#!/usr/bin/env python3
import sqlite3
import json
import os
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'team.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT NOT NULL,
            phone TEXT,
            grade INTEGER NOT NULL,
            position TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '在队'
        );

        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tdate TEXT NOT NULL,
            ttype TEXT NOT NULL,
            duration INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS training_attendance (
            training_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            PRIMARY KEY (training_id, player_id),
            FOREIGN KEY (training_id) REFERENCES trainings(id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opponent TEXT NOT NULL,
            gdate TEXT NOT NULL,
            home_away TEXT NOT NULL,
            our_score INTEGER NOT NULL DEFAULT 0,
            opp_score INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS game_roster (
            game_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            PRIMARY KEY (game_id, player_id),
            FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
        );
    ''')
    conn.commit()
    conn.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        if not os.path.isfile(path):
            self.send_response(404)
            self.end_headers()
            return
        ctype = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        with open(path, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', ctype + ('; charset=utf-8' if ctype.startswith('text/') else ''))
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode('utf-8'))
        except Exception:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == '/' or path == '':
            self._send_file(os.path.join(os.path.dirname(__file__), 'index.html'))
            return
        if path in ('/app.js', '/style.css'):
            self._send_file(os.path.join(os.path.dirname(__file__), path.lstrip('/')))
            return

        if path == '/api/players':
            conn = get_db()
            rows = conn.execute('SELECT * FROM players ORDER BY id').fetchall()
            conn.close()
            self._send_json([dict(r) for r in rows])
            return

        if path == '/api/trainings':
            conn = get_db()
            rows = conn.execute('SELECT * FROM trainings ORDER BY tdate DESC, id DESC').fetchall()
            result = []
            for r in rows:
                d = dict(r)
                att = conn.execute(
                    'SELECT p.id, p.nickname FROM training_attendance ta '
                    'JOIN players p ON p.id = ta.player_id WHERE ta.training_id = ?',
                    (r['id'],)
                ).fetchall()
                d['attendance'] = [dict(a) for a in att]
                result.append(d)
            conn.close()
            self._send_json(result)
            return

        if path == '/api/games':
            conn = get_db()
            rows = conn.execute('SELECT * FROM games ORDER BY gdate DESC, id DESC').fetchall()
            result = []
            for r in rows:
                d = dict(r)
                rost = conn.execute(
                    'SELECT p.id, p.nickname FROM game_roster gr '
                    'JOIN players p ON p.id = gr.player_id WHERE gr.game_id = ?',
                    (r['id'],)
                ).fetchall()
                d['roster'] = [dict(a) for a in rost]
                result.append(d)
            conn.close()
            self._send_json(result)
            return

        if path == '/api/stats/player-month':
            player_id = int(qs.get('player_id', [0])[0])
            year = int(qs.get('year', [datetime.now().year])[0])
            month = int(qs.get('month', [datetime.now().month])[0])
            prefix = f"{year:04d}-{month:02d}"
            conn = get_db()
            t_count = conn.execute(
                'SELECT COUNT(*) FROM training_attendance ta '
                'JOIN trainings t ON t.id = ta.training_id '
                'WHERE ta.player_id = ? AND SUBSTR(t.tdate, 1, 7) = ?',
                (player_id, prefix)
            ).fetchone()[0]
            g_count = conn.execute(
                'SELECT COUNT(*) FROM game_roster gr '
                'JOIN games g ON g.id = gr.game_id '
                'WHERE gr.player_id = ? AND SUBSTR(g.gdate, 1, 7) = ?',
                (player_id, prefix)
            ).fetchone()[0]
            conn.close()
            self._send_json({'player_id': player_id, 'trainings': t_count, 'games': g_count})
            return

        if path == '/api/stats/training-month':
            year = int(qs.get('year', [datetime.now().year])[0])
            month = int(qs.get('month', [datetime.now().month])[0])
            prefix = f"{year:04d}-{month:02d}"
            conn = get_db()
            rows = conn.execute(
                'SELECT ttype, COUNT(*) as cnt, SUM(duration) as total_dur '
                'FROM trainings WHERE SUBSTR(tdate, 1, 7) = ? GROUP BY ttype',
                (prefix,)
            ).fetchall()
            conn.close()
            self._send_json([dict(r) for r in rows])
            return

        if path == '/api/stats/win-loss':
            conn = get_db()
            wins = conn.execute("SELECT COUNT(*) FROM games WHERE our_score > opp_score").fetchone()[0]
            losses = conn.execute("SELECT COUNT(*) FROM games WHERE our_score < opp_score").fetchone()[0]
            draws = conn.execute("SELECT COUNT(*) FROM games WHERE our_score = opp_score").fetchone()[0]
            total = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
            conn.close()
            self._send_json({'wins': wins, 'losses': losses, 'draws': draws, 'total': total})
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()
        conn = get_db()

        try:
            if path == '/api/players':
                cur = conn.execute(
                    'INSERT INTO players (nickname, phone, grade, position, status) VALUES (?, ?, ?, ?, ?)',
                    (body.get('nickname', ''), body.get('phone', ''),
                     int(body.get('grade', 0)), body.get('position', ''),
                     body.get('status', '在队'))
                )
                conn.commit()
                pid = cur.lastrowid
                row = conn.execute('SELECT * FROM players WHERE id = ?', (pid,)).fetchone()
                self._send_json(dict(row))
                return

            if path == '/api/trainings':
                cur = conn.execute(
                    'INSERT INTO trainings (tdate, ttype, duration) VALUES (?, ?, ?)',
                    (body.get('tdate', ''), body.get('ttype', ''),
                     int(body.get('duration', 0)))
                )
                tid = cur.lastrowid
                att_ids = body.get('attendance_ids', []) or []
                for pid in att_ids:
                    conn.execute(
                        'INSERT OR IGNORE INTO training_attendance (training_id, player_id) VALUES (?, ?)',
                        (tid, int(pid))
                    )
                conn.commit()
                row = conn.execute('SELECT * FROM trainings WHERE id = ?', (tid,)).fetchone()
                result = dict(row)
                att = conn.execute(
                    'SELECT p.id, p.nickname FROM training_attendance ta '
                    'JOIN players p ON p.id = ta.player_id WHERE ta.training_id = ?',
                    (tid,)
                ).fetchall()
                result['attendance'] = [dict(a) for a in att]
                self._send_json(result)
                return

            if path == '/api/games':
                cur = conn.execute(
                    'INSERT INTO games (opponent, gdate, home_away, our_score, opp_score) VALUES (?, ?, ?, ?, ?)',
                    (body.get('opponent', ''), body.get('gdate', ''),
                     body.get('home_away', '主场'),
                     int(body.get('our_score', 0)), int(body.get('opp_score', 0)))
                )
                gid = cur.lastrowid
                roster_ids = body.get('roster_ids', []) or []
                for pid in roster_ids:
                    conn.execute(
                        'INSERT OR IGNORE INTO game_roster (game_id, player_id) VALUES (?, ?)',
                        (gid, int(pid))
                    )
                conn.commit()
                row = conn.execute('SELECT * FROM games WHERE id = ?', (gid,)).fetchone()
                result = dict(row)
                rost = conn.execute(
                    'SELECT p.id, p.nickname FROM game_roster gr '
                    'JOIN players p ON p.id = gr.player_id WHERE gr.game_id = ?',
                    (gid,)
                ).fetchall()
                result['roster'] = [dict(a) for a in rost]
                self._send_json(result)
                return

            self.send_response(404)
            self.end_headers()
        except Exception as e:
            conn.rollback()
            self._send_json({'error': str(e)}, 400)
        finally:
            conn.close()

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()
        conn = get_db()

        try:
            parts = path.strip('/').split('/')
            if len(parts) == 3 and parts[0] == 'api':
                resource = parts[1]
                rid = int(parts[2])

                if resource == 'players':
                    conn.execute(
                        'UPDATE players SET nickname=?, phone=?, grade=?, position=?, status=? WHERE id=?',
                        (body.get('nickname', ''), body.get('phone', ''),
                         int(body.get('grade', 0)), body.get('position', ''),
                         body.get('status', '在队'), rid)
                    )
                    conn.commit()
                    row = conn.execute('SELECT * FROM players WHERE id = ?', (rid,)).fetchone()
                    if row:
                        self._send_json(dict(row))
                    else:
                        self._send_json({'error': 'not found'}, 404)
                    return

                if resource == 'trainings':
                    conn.execute(
                        'UPDATE trainings SET tdate=?, ttype=?, duration=? WHERE id=?',
                        (body.get('tdate', ''), body.get('ttype', ''),
                         int(body.get('duration', 0)), rid)
                    )
                    conn.execute('DELETE FROM training_attendance WHERE training_id = ?', (rid,))
                    att_ids = body.get('attendance_ids', []) or []
                    for pid in att_ids:
                        conn.execute(
                            'INSERT OR IGNORE INTO training_attendance (training_id, player_id) VALUES (?, ?)',
                            (rid, int(pid))
                        )
                    conn.commit()
                    row = conn.execute('SELECT * FROM trainings WHERE id = ?', (rid,)).fetchone()
                    if row:
                        result = dict(row)
                        att = conn.execute(
                            'SELECT p.id, p.nickname FROM training_attendance ta '
                            'JOIN players p ON p.id = ta.player_id WHERE ta.training_id = ?',
                            (rid,)
                        ).fetchall()
                        result['attendance'] = [dict(a) for a in att]
                        self._send_json(result)
                    else:
                        self._send_json({'error': 'not found'}, 404)
                    return

                if resource == 'games':
                    conn.execute(
                        'UPDATE games SET opponent=?, gdate=?, home_away=?, our_score=?, opp_score=? WHERE id=?',
                        (body.get('opponent', ''), body.get('gdate', ''),
                         body.get('home_away', '主场'),
                         int(body.get('our_score', 0)), int(body.get('opp_score', 0)), rid)
                    )
                    conn.execute('DELETE FROM game_roster WHERE game_id = ?', (rid,))
                    roster_ids = body.get('roster_ids', []) or []
                    for pid in roster_ids:
                        conn.execute(
                            'INSERT OR IGNORE INTO game_roster (game_id, player_id) VALUES (?, ?)',
                            (rid, int(pid))
                        )
                    conn.commit()
                    row = conn.execute('SELECT * FROM games WHERE id = ?', (rid,)).fetchone()
                    if row:
                        result = dict(row)
                        rost = conn.execute(
                            'SELECT p.id, p.nickname FROM game_roster gr '
                            'JOIN players p ON p.id = gr.player_id WHERE gr.game_id = ?',
                            (rid,)
                        ).fetchall()
                        result['roster'] = [dict(a) for a in rost]
                        self._send_json(result)
                    else:
                        self._send_json({'error': 'not found'}, 404)
                    return

            self.send_response(404)
            self.end_headers()
        except Exception as e:
            conn.rollback()
            self._send_json({'error': str(e)}, 400)
        finally:
            conn.close()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        conn = get_db()
        try:
            parts = path.strip('/').split('/')
            if len(parts) == 3 and parts[0] == 'api':
                resource = parts[1]
                rid = int(parts[2])
                if resource == 'players':
                    conn.execute('DELETE FROM players WHERE id = ?', (rid,))
                elif resource == 'trainings':
                    conn.execute('DELETE FROM trainings WHERE id = ?', (rid,))
                elif resource == 'games':
                    conn.execute('DELETE FROM games WHERE id = ?', (rid,))
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                conn.commit()
                self._send_json({'ok': True})
                return
            self.send_response(404)
            self.end_headers()
        except Exception as e:
            conn.rollback()
            self._send_json({'error': str(e)}, 400)
        finally:
            conn.close()


def main():
    init_db()
    host = 'localhost'
    port = 5938
    print(f"轮椅篮球队管理系统启动: http://{host}:{port}")
    HTTPServer((host, port), Handler).serve_forever()


if __name__ == '__main__':
    main()
