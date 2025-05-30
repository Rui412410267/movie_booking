from flask import Flask, render_template, request, redirect, url_for
import pymysql
from decimal import Decimal

app = Flask(__name__)

# 連線資料庫
def get_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='0000',  # ← 改成你自己的 MySQL 密碼
        database='movie_booking',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# 首頁：顯示所有電影與場次（用 LEFT JOIN 顯示全部電影）
@app.route("/")
def index():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.movie_id, m.title, m.genre,
               s.showtime_id, s.show_date, s.show_time,
               t.name AS theater
        FROM Movie m
        LEFT JOIN Showtime s ON m.movie_id = s.movie_id
        LEFT JOIN Theater t ON s.theater_id = t.theater_id
        ORDER BY m.movie_id, s.show_time
    """)
    movies = cursor.fetchall()
    conn.close()
    return render_template("index.html", movies=movies)


# 顯示場次與餐點頁
@app.route("/showtime/<int:showtime_id>")
def showtime(showtime_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.showtime_id, m.title, t.name AS theater, s.show_date, s.show_time
        FROM Showtime s
        JOIN Movie m ON s.movie_id = m.movie_id
        JOIN Theater t ON s.theater_id = t.theater_id
        WHERE s.showtime_id = %s
    """, (showtime_id,))
    showtime = cursor.fetchone()

    cursor.execute("SELECT * FROM Seat WHERE showtime_id = %s ORDER BY seat_number", (showtime_id,))
    seats = cursor.fetchall()

    cursor.execute("SELECT * FROM FoodItem")
    food_items = cursor.fetchall()

    conn.close()
    return render_template("showtime.html", showtime=showtime, seats=seats, food_items=food_items)



# 訂票與餐點處理
@app.route("/place_order", methods=["POST"])
def place_order():
    showtime_id = request.form.get("showtime_id")
    selected_seats = request.form.getlist("seats")  # 多選座位

    conn = get_connection()
    cursor = conn.cursor()

    # 餐點資料
    cursor.execute("SELECT food_id, name, price FROM FoodItem")
    food_items = cursor.fetchall()

    ticket_price = Decimal('300.00')
    num_tickets = len(selected_seats)
    ticket_total = ticket_price * num_tickets
    food_total = Decimal('0.00')

    ordered_food = []
    for item in food_items:
        qty = int(request.form.get(f"food_{item['food_id']}", 0))
        if qty > 0:
            subtotal = item['price'] * qty
            ordered_food.append({
                'name': item['name'],
                'qty': qty,
                'price': item['price'],
                'subtotal': subtotal
            })
            food_total += subtotal

    total_price = ticket_total + food_total

    # 建立訂單
    cursor.execute("INSERT INTO Orders (total_price) VALUES (%s)", (total_price,))
    order_id = cursor.lastrowid

    # 餐點明細
    for food in ordered_food:
        cursor.execute("""
            INSERT INTO Order_Food (order_id, food_id, quantity)
            VALUES (%s, (SELECT food_id FROM FoodItem WHERE name = %s), %s)
        """, (order_id, food['name'], food['qty']))

    # 訂票明細與更新座位狀態
    for seat in selected_seats:
        cursor.execute("""
            INSERT INTO Order_Ticket (order_id, showtime_id, seat, ticket_price)
            VALUES (%s, %s, %s, %s)
        """, (order_id, showtime_id, seat, ticket_price))

        cursor.execute("""
            UPDATE Seat SET is_reserved = TRUE
            WHERE showtime_id = %s AND seat_number = %s
        """, (showtime_id, seat))

    conn.commit()
    conn.close()

    # 顯示總結資訊
    summary = f"""
        <h1>✅ 訂購成功！</h1>
        <p><strong>訂單編號：</strong>{order_id}</p>
        <p><strong>票價：</strong>{ticket_price} x {num_tickets} = {ticket_total} 元</p>
        <p><strong>餐點：</strong>{food_total} 元</p>
        <p><strong>總金額：</strong><span style='color:red;'>{total_price} 元</span></p>
        <a href="/">回首頁</a>
    """
    return summary


# 啟動伺服器
if __name__ == "__main__":
    app.run(debug=True , port=5000)

