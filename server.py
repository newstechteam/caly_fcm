import json
import os
import firebase_admin
from firebase_admin import credentials, messaging
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# 🔵 Flask 서버 초기화
app = Flask(__name__)
app.secret_key = "your_secret_key"  # 보안 강화를 위한 세션 키

# 🔵 환경 변수에서 Firebase JSON 로드 (Render Secret Files 사용)
firebase_json = os.getenv("FIREBASE_CONFIG")  # 환경 변수에서 JSON 불러오기
if not firebase_json:
    raise ValueError("❌ 환경 변수 FIREBASE_CONFIG가 설정되지 않았습니다!")

# 🔵 Firebase Admin SDK 초기화
cred = credentials.Certificate(json.loads(firebase_json))  # 🔥 JSON 직접 로드
firebase_admin.initialize_app(cred)

# 🔵 사용자 계정 정보 (아이디: NCENTER, 비밀번호: NEWS!1234)
users = {
    "NCENTER": generate_password_hash("NEWS!1234")  # 기본 로그인 계정
}

# 🔵 로그인 페이지
@app.route("/", methods=["GET", "POST"])
@Limiter.limit("5 per minute")  # 1분에 5번 이상 로그인 시도 차단
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username in users and check_password_hash(users[username], password):
            session["user"] = username
            return redirect(url_for("home"))  # 로그인 성공 시 메인 페이지 이동
        else:
            error = "❌ 로그인 실패! 다시 시도하세요."

    return render_template_string(login_html, error=error)

# 🔵 로그인한 사용자만 접근 가능
@app.route("/home")
def home():
    if "user" not in session:
        return redirect(url_for("login"))

    return render_template_string(fcm_html)  # 로그인 성공 시 FCM 페이지 로드

# 🔵 로그아웃 기능
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# 🔵 로그인 HTML
login_html = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>로그인</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .login-container { width: 500px; background: white; padding: 40px; border-radius: 10px; box-shadow: 0px 0px 20px rgba(0, 0, 0, 0.1); }
        .btn-custom { width: 100%; font-size: 20px; padding: 10px; }
        .form-control { font-size: 18px; padding: 12px; }
        .error-message { color: red; text-align: center; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="login-container">
        <h3 class="text-center mb-4">🔒 로그인</h3>
        {% if error %}
            <p class="error-message">{{ error }}</p>
        {% endif %}
        <form method="post">
            <div class="mb-3">
                <label class="form-label">아이디</label>
                <input type="text" name="username" class="form-control" required placeholder="아이디 입력">
            </div>
            <div class="mb-3">
                <label class="form-label">비밀번호</label>
                <input type="password" name="password" class="form-control" required placeholder="비밀번호 입력">
            </div>
            <button type="submit" class="btn btn-primary btn-custom">🚀 로그인</button>
        </form>
    </div>
</body>
</html>
"""

# 🔵 FCM 알림 전송 HTML
fcm_html = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FCM 알림 보내기</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .container { max-width: 650px; background: white; padding: 30px; border-radius: 10px; box-shadow: 0px 0px 20px rgba(0, 0, 0, 0.1); }
        .form-control { font-size: 16px; }
        .btn-custom { width: 100%; font-size: 18px; }
    </style>
</head>
<body>
    <div class="container">
        <h3 class="text-center mb-4">🔥 Caly 알림 보내기</h3>
        <form id="notificationForm">
            <div class="mb-3">
                <label class="form-label">제목</label>
                <input type="text" id="title" class="form-control" required placeholder="알림 제목 입력">
            </div>
            <div class="mb-3">
                <label class="form-label">내용</label>
                <textarea id="body" class="form-control" rows="10" required placeholder="알림 내용 입력"></textarea>
            </div>
            <button type="button" class="btn btn-primary btn-custom" onclick="sendNotification()">🚀 전송</button>
        </form>
        <a href="/logout" class="btn btn-danger mt-3 btn-custom">🔒 로그아웃</a>
    </div>

    <script>
        function sendNotification() {
            const title = document.getElementById("title").value;
            const body = document.getElementById("body").value;

            fetch("/send", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title, body })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert("✅ 전송 성공!");
                } else {
                    alert("❌ 전송 실패: " + data.error);
                }
            })
            .catch(error => alert("❌ 오류 발생: " + error));
        }
    </script>
</body>
</html>
"""

# 🔵 FCM 알림 전송 함수
def send_fcm_notification(title, body):
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        topic="all"
    )
    response = messaging.send(message)
    return f"✅ FCM 메시지 전송 완료! 응답 ID: {response}"

# 🔵 POST 요청을 받아서 FCM 알림 전송
@app.route("/send", methods=["POST"])
def send_notification():
    if "user" not in session:
        return jsonify({"success": False, "error": "로그인이 필요합니다."}), 403

    data = request.get_json()
    title = data.get("title", "기본 제목")
    body = data.get("body", "기본 내용")

    try:
        result = send_fcm_notification(title, body)
        return jsonify({"success": True, "message": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# 🔵 Flask 서버 실행
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))  # 환경 변수에서 PORT 값 가져오기, 없으면 5000 사용
    app.run(debug=True, host="0.0.0.0", port=port)  # 🔴 변경된 부분!
