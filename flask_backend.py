from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from database_manager import DatabaseManager
from order_manager import OrderManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  
socketio = SocketIO(app)
db_manager = DatabaseManager('my_items_database.db')
order_manager = OrderManager(tax_rate=0.08)  

@app.route('/')
def index():
    print("DEBUG flask_backend serve html")
    return app.send_static_file('index.html')

@app.route('/add-item', methods=['POST'])
def add_item():
    print("DEBUG flask_backend add item")

    barcode = request.json['barcode']
    item_details = db_manager.get_item_details(barcode)
    if item_details:
        order_manager.add_item({'name': item_details[0], 'price': item_details[1]})
        return jsonify({'success': True, 'item': item_details})
    return jsonify({'success': False, 'error': 'Item not found'})

@app.route('/checkout', methods=['GET'])
def checkout():
    print("DEBUG flask_backend checkout")

    total = order_manager.calculate_total_with_tax()
    return jsonify({'total': total})

@app.route('/barcode-scanned', methods=['POST'])
def barcode_scanned():
    print("DEBUG flask_backend barcode_scanned")
    barcode = request.json['barcode']
    
    
    item_details = db_manager.get_item_details(barcode)
    if item_details:
        socketio.emit('item_details', {'name': item_details[0], 'price': item_details[1]})
    else:
        socketio.emit('item_not_found', {'barcode': barcode})
    return jsonify({'success': True})

@socketio.on('scan_barcode')
def handle_scan(data):
    barcode = data['barcode']
    item_details = db_manager.get_item_details(barcode)
    if item_details:
        socketio.emit('item_details', {'name': item_details[0], 'price': item_details[1]})
    else:
        socketio.emit('item_not_found', {'barcode': barcode})
def run_flask_app():
    print("DEBUG flask_backend run_flask_app")
    socketio.run(app, debug=True, use_reloader=False)
if __name__ == '__main__':
    socketio.run(app, debug=True)
