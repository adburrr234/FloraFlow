# transactions.py
import pymysql

def process_plant_sale(connection, sale_id, plant_id, quantity, price):
    try:
        with connection.cursor() as cursor:
            # Start the transaction
            connection.begin()

            # 1. Insert into SaleDetails
            insert_sql = "INSERT INTO SaleDetails (saleId, plantId, quantity, price) VALUES (%s, %s, %s, %s)"
            cursor.execute(insert_sql, (sale_id, plant_id, quantity, price))

            # 2. Update Plants quantity
            update_sql = "UPDATE Plants SET quantity = quantity - %s WHERE plantId = %s"
            cursor.execute(update_sql, (quantity, plant_id))

            # Commit the transaction if both succeed
            connection.commit()
            return True
            
    except pymysql.MySQLError as e:
        # Roll back all changes if any error occurs
        connection.rollback()
        print(f"Sale transaction failed: {e}")
        return False

def process_plant_purchase(connection, purchase_id, plant_id, quantity, cost):
    try:
        with connection.cursor() as cursor:
            connection.begin()
            
            insert_sql = "INSERT INTO PurchasePlantDetails (purchaseId, plantId, quantity, cost) VALUES (%s, %s, %s, %s)"
            cursor.execute(insert_sql, (purchase_id, plant_id, quantity, cost))
            
            update_sql = "UPDATE Plants SET quantity = quantity + %s WHERE plantId = %s"
            cursor.execute(update_sql, (quantity, plant_id))
            
            connection.commit()
            return True
    except pymysql.MySQLError as e:
        connection.rollback()
        print(f"Plant purchase transaction failed: {e}")
        return False

def process_accessory_purchase(connection, purchase_id, accessory_id, quantity, cost):
    try:
        with connection.cursor() as cursor:
            connection.begin()
            
            insert_sql = "INSERT INTO PurchaseAccessoryDetails (purchaseId, accessoryId, quantity, cost) VALUES (%s, %s, %s, %s)"
            cursor.execute(insert_sql, (purchase_id, accessory_id, quantity, cost))
            
            update_sql = "UPDATE Accessories SET quantity = quantity + %s WHERE accessoryId = %s"
            cursor.execute(update_sql, (quantity, accessory_id))
            
            connection.commit()
            return True
    except pymysql.MySQLError as e:
        connection.rollback()
        print(f"Accessory purchase transaction failed: {e}")
        return False