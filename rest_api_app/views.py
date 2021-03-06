from rest_framework import status
from rest_framework.response import Response

from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework import permissions
from rest_framework.authentication import TokenAuthentication

from rest_api_app.models import Table, MyUser, Order, TableRequest, Receipt, MyUserManager
from rest_api_app.serializers import UserSerializer, TableSerializer, OrderSerializer, ReceiptSerializer

from django.db.models import Sum
from django.db.models import F

from django.db import IntegrityError

@api_view()
def api_root(request):
    """ tablemate API """
    return Response({
        "login": "http://127.0.0.1:8000/login/"
    })

@api_view(["GET"])
def get_all_users(request):
    users = MyUser.objects.all()
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)

@api_view(["POST"])
def login(request):
    email = request.data.get("email")
    password = request.data.get("password")

    try:
        user = MyUser.objects.get(email=email)
        if user.check_password(password):
            token = Token.objects.get_or_create(user=user)
            
            return Response({
                "auth_token": token[0].key,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "user_id": user.id
            }, status=status.HTTP_200_OK)

    except MyUser.DoesNotExist:
        return Response({"error": "There was a problem"}, status=status.HTTP_404_NOT_FOUND)

@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response({"success": "Logged out successfully"})

@api_view(["POST"])
def register(request):
    first_name = request.data.get("first_name")
    last_name = request.data.get("last_name")
    email = request.data.get("email")
    password = request.data.get("password")
    
    try:
        user = MyUser.objects.create_user(first_name, last_name, email, password)
        token = Token.objects.get_or_create(user=user)

        return Response({
            "auth_token": token[0].key,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "user_id": user.id
        }, status=status.HTTP_201_CREATED)

    except IntegrityError:
        return Response({"error": "Email is already in use"}, status=status.HTTP_409_CONFLICT)

@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def get_user_info(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def create_or_join_table(request):
    # Find server id to assign
    address_table_combo = request.data.get("address_table_combo")
    restaurant_address = request.data.get("restaurant_address")
    restaurant_name = request.data.get("restaurant_name")
    server = find_server(restaurant_address)
    server_id = server.get("server_id")

    if server_id == -1:
        return Response({"error": "Something went wrong"}, status=status.HTTP_409_CONFLICT)

    # Attempt to create table, if does not exist
    table, created = Table.objects.get_or_create(
        address_table_combo=address_table_combo,
    )
    if not created:
        table.party_size += 1
    else:
        table.server_id = server_id
        table.server_name = server.get("server_name")
        table.restaurant_name = restaurant_name
        table.restaurant_address = restaurant_address
    table.save()

    MyUser.objects.filter(id=request.data.get("user_id")).update(
        address_table_combo=address_table_combo,
        active_table_number=request.data.get("table_number"),
        active_restaurant=restaurant_address,
        active_table_id=table.id,
        current_server_id=server.get("server_id")
    )
    
    return Response({
        "message": "Joined table",
        "party_size": table.party_size,
        "restaurant_name": table.restaurant_name,
        "restaurant_address": table.restaurant_address,
        "server_id": table.server_id,
        "server_name": table.server_name,
        "address_table_combo": table.address_table_combo,
    }, status=status.HTTP_200_OK)

@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def delete_table(request):
    Table.objects.filter(address_table_combo=request.data.get("address_table_combo")).delete()
    return Response({"success": "Table deleted"}, status=status.HTTP_200_OK)

@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def get_all_tables(request):
    serializer = TableSerializer(Table.objects.all(), many=True)
    return Response(serializer.data)

@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def get_server_tables(request):
    tables = Table.objects.filter(server_id=request.user.id)
    serializer = TableSerializer(tables, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def get_users_at_table(request):
    users = MyUser.objects.filter(address_table_combo=request.data.get("address_table_combo"))
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)

@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def request_service(request):
    address_table_combo = request.data.get("address_table_combo")

    table_request, created = TableRequest.objects.get_or_create(
        address_table_combo=address_table_combo,
    )
    if created:
        table = get_table_object(address_table_combo)
        
        if table is not None:
            table.request_made = True
            table.save()

        return Response({"success": "Request made"}, status=status.HTTP_200_OK)
    else:
        return Response({"error": "Request already made"}, status=status.HTTP_409_CONFLICT)

@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def serve_request(request):
    address_table_combo = request.data.get("address_table_combo")
    TableRequest.objects.filter(address_table_combo=address_table_combo).delete()

    table = get_table_object(address_table_combo)
        
    if table is not None:
        table.request_made = False
        table.save()

    return Response({"success": "Request served"}, status=status.HTTP_200_OK)

@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def has_request(request):
    return Response({
        "request_made": TableRequest.objects
        .filter(address_table_combo=request.data.get("address_table_combo"))
        .exists()
    })

def find_server(restaurant_address):
    servers = list(MyUser.objects.filter(working_restaurant=restaurant_address, is_working=True))
    
    if not servers:
        return {"server_id": -1, "server_name": ""}

    min_load_server_id = -1
    min_load = 10000
    
    for server in servers:
        load = Table.objects.filter(server_id=server.id).count()
        if load < min_load:
            min_load = load
            min_load_server_id = server.id

    return {"server_id": min_load_server_id, "server_name": server.first_name}

@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def get_server_id(request):
    return Response({"server_id": request.user.current_server_id}, status=status.HTTP_200_OK)

@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def place_order(request):
    """ Provide order_name, order_price, customer_first_name, address_table_combo, restaurant_address table_number """
    # Check if table exists first?

    serializer = OrderSerializer(data=request.data)
    if (serializer.is_valid()):
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.error, status=status.HTTP_400_BAD_REQUEST)

@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def queue_order(request):
    Order.objects.get(id=request.data.get("id")).update(new_order=False, order_queued=True)
    return Response({"message": "Order queued"}, status=status.HTTP_200_OK)

@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def order_delivered(request):
    Order.objects.get(id=request.data.get("id")).update(order_queued=False, payment_pending=True)
    return Response({"message": "Order delivered, payment pending"}, status=status.HTTP_200_OK)

@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def finish_and_pay(request):
    address_table_combo = request.data.get("address_table_combo")
    table = get_table_object(address_table_combo)

    if table is None:
        return Response({"error": "Table does not exist"}, status=status.HTTP_404_NOT_FOUND)

    user_id = request.data.get("user_id")
    orders = Order.objects.filter(
        customer_id=user_id, address_table_combo=address_table_combo, active_order=True)

    total = 0.00
    if orders.exists():
        subtotal = orders.aggregate(Sum("order_price")).get("order_price__sum", 0.00)

        # Add tax, attempt payment
        total = subtotal

        # If payment successful
    
    # Assuming payment was successful
    table.party_size -= 1
    table.save()
    
    if table.party_size == 0:
        table.delete()   

    receipt = Receipt(
        customer_id=user_id,
        total_bill=total,
        server_name=request.data.get("server_name"),
        restaurant_name=request.data.get("restaurant_name"),
        restaurant_address=request.data.get("restaurant_address"),
    )
    receipt.save()
    orders.update(payment_pending=False, active_order=False, receipt_id=receipt.id)

    return Response({"message": "Payment successful", "bill": total}, status=status.HTTP_200_OK)

@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def get_table_orders(request):
    address_table_combo = request.data.get("address_table_combo")
    orders = Order.objects.filter(address_table_combo=address_table_combo, active_order=True)
    serializer = OrderSerializer(orders, many=True)
    return Response(serializer.data)

@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def get_table(request):
    table_id = request.user.active_table_id
    
    if table_id == -1:
        return Response({"error": "No active table"}, status=status.HTTP_404_NOT_FOUND)

    try:
        table = Table.objects.get(id=table_id)
        serializer = TableSerializer(table)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Table.DoesNotExist:
        return Response({"error": "Table does not exist"}, status=status.HTTP_404_NOT_FOUND)

def get_table_object(address_table_combo):
    try:
        table = Table.objects.get(address_table_combo=address_table_combo)
        return table
    except Table.DoesNotExist:
        None

@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def get_active_table_id(request):
    return Response({"table_id": request.user.active_table_id}, status=status.HTTP_200_OK)

@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def get_receipts(request):
    receipts = Receipt.objects.filter(customer_id=request.data.get("user_id"))
    serializer = ReceiptSerializer(receipts, many=True)
    return Response(serializer.data)

@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def get_orders(request):
    orders = Order.objects.filter(customer_id=request.data.get("user_id"))
    serializer = OrderSerializer(orders, many=True)
    return Response(serializer.data)

@api_view(["POST"])
def create_test_server(request):
    first_name = "William"
    last_name = "Woodhouse"
    email = "woodhouse@gmail.com"
    password = "12345"
    
    try:
        user = MyUser.objects.create_user(first_name, last_name, email, password)
        user.is_server = True
        user.is_working = True
        user.working_restaurant = "1234 Restaurant St."
        user.save()
        token = Token.objects.get_or_create(user=user)

        return Response({
            "auth_token": token[0].key,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "user_id": user.id
        }, status=status.HTTP_201_CREATED)

    except IntegrityError:
        return Response({"error": "Email is already in use"}, status=status.HTTP_409_CONFLICT)
