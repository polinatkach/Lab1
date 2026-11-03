"""Лабораторная работа № 1. Ресторан.

Программа хранит клиентов, официантов, столики, меню, блюда,
продукты, брони и заказы. Данные сохраняются в JSON и XML.

Запуск:
    python main.py --demo
"""
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime


# ---------------------------------------------------------------------------
# 1. Ошибки
# ---------------------------------------------------------------------------

class RestaurantError(Exception):
    """Главная ошибка программы, остальные от неё наследуются."""
    pass


class EntityNotFoundError(RestaurantError):
    """Не нашли объект по ID."""
    pass


class DuplicateEntityError(RestaurantError):
    """Такой ID или такой объект уже есть."""
    pass


class ValidationError(RestaurantError):
    """Неправильные данные."""
    pass


class StorageError(RestaurantError):
    """Не получилось прочитать или записать файл."""
    pass


# ---------------------------------------------------------------------------
# 2. Функции проверки данных
# ---------------------------------------------------------------------------

def check_text(value, name):
    # строка не должна быть пустой
    if not isinstance(value, str):
        raise ValidationError("Поле «" + name + "» должно быть строкой.")
    value = value.strip()
    if value == "":
        raise ValidationError("Поле «" + name + "» не может быть пустым.")
    return value


def check_id(value, name="ID"):
    # type() is int отсеивает и True/False
    if type(value) is not int or value <= 0:
        raise ValidationError(name + " должен быть положительным целым числом.")
    return value


def check_number(value, name):
    # число не меньше нуля (цены, остатки)
    if type(value) not in (int, float) or value < 0:
        raise ValidationError(name + " должно быть неотрицательным числом.")
    return float(value)


def check_date(value, date_format, message):
    # проверяем, что строка подходит под формат даты
    try:
        datetime.strptime(value, date_format)
    except (TypeError, ValueError):
        raise ValidationError(message)


# Допустимые статусы
RESERVATION_STATUSES = ["Запланирована", "Завершена", "Отменена"]
ORDER_STATUSES = ["Открыт", "Оплачен", "Отменён"]


# ---------------------------------------------------------------------------
# 3. Классы объектов
# У каждого: __init__ (создание + проверка) и to_dict (превращение в словарь)
# ---------------------------------------------------------------------------

class Entity:
    """Общий родитель, чтобы не писать to_dict в каждом классе."""

    def to_dict(self):
        return dict(self.__dict__)


class DishCategory(Entity):
    def __init__(self, id, name, description=""):
        check_id(id)
        self.id = id
        self.name = check_text(name, "Название категории")
        self.description = description


class Menu(Entity):
    def __init__(self, id, name, description=""):
        check_id(id)
        self.id = id
        self.name = check_text(name, "Название меню")
        self.description = description


class Hall(Entity):
    def __init__(self, id, name, location):
        check_id(id)
        self.id = id
        self.name = check_text(name, "Название зала")
        self.location = check_text(location, "Расположение")


class Table(Entity):
    def __init__(self, id, hall_id, number, seats):
        check_id(id)
        check_id(hall_id, "ID зала")
        check_id(number, "Номер столика")
        check_id(seats, "Количество мест")
        self.id = id
        self.hall_id = hall_id
        self.number = number
        self.seats = seats


class Customer(Entity):
    def __init__(self, id, full_name, phone, loyalty_card=""):
        check_id(id)
        self.id = id
        self.full_name = check_text(full_name, "ФИО клиента")
        self.phone = check_text(phone, "Телефон")
        self.loyalty_card = loyalty_card


class Waiter(Entity):
    def __init__(self, id, full_name, hall_id, position):
        check_id(id)
        check_id(hall_id, "ID зала")
        self.id = id
        self.full_name = check_text(full_name, "ФИО официанта")
        self.hall_id = hall_id
        self.position = check_text(position, "Должность")


class Shift(Entity):
    def __init__(self, id, waiter_id, weekdays, start_time, end_time):
        check_id(id)
        check_id(waiter_id, "ID официанта")
        self.id = id
        self.waiter_id = waiter_id
        self.weekdays = check_text(weekdays, "Дни недели")
        check_date(start_time, "%H:%M", "Время смены должно быть в формате ЧЧ:ММ.")
        check_date(end_time, "%H:%M", "Время смены должно быть в формате ЧЧ:ММ.")
        # время вида ЧЧ:ММ можно сравнивать как строки
        if start_time >= end_time:
            raise ValidationError("Начало смены должно быть раньше её окончания.")
        self.start_time = start_time
        self.end_time = end_time


class Product(Entity):
    def __init__(self, id, name, unit, stock=0.0):
        check_id(id)
        self.id = id
        self.name = check_text(name, "Название продукта")
        self.unit = check_text(unit, "Единица измерения")
        self.stock = check_number(stock, "Остаток на складе")


class Dish(Entity):
    def __init__(self, id, name, price, menu_id, category_id, description=""):
        check_id(id)
        check_id(menu_id, "ID меню")
        check_id(category_id, "ID категории")
        self.id = id
        self.name = check_text(name, "Название блюда")
        self.price = check_number(price, "Цена блюда")
        self.menu_id = menu_id
        self.category_id = category_id
        self.description = description


class DishIngredient(Entity):
    def __init__(self, id, dish_id, product_id, amount):
        check_id(id)
        check_id(dish_id, "ID блюда")
        check_id(product_id, "ID продукта")
        amount = check_number(amount, "Количество продукта")
        if amount == 0:
            raise ValidationError("Количество продукта должно быть больше нуля.")
        self.id = id
        self.dish_id = dish_id
        self.product_id = product_id
        self.amount = amount


class Reservation(Entity):
    def __init__(self, id, customer_id, table_id, start_at, guests, status="Запланирована"):
        check_id(id)
        check_id(customer_id, "ID клиента")
        check_id(table_id, "ID столика")
        check_id(guests, "Количество гостей")
        if status not in RESERVATION_STATUSES:
            raise ValidationError("Статус брони: Запланирована, Завершена или Отменена.")
        check_date(start_at, "%Y-%m-%d %H:%M",
                   "Дата и время брони должны быть в формате ГГГГ-ММ-ДД ЧЧ:ММ.")
        self.id = id
        self.customer_id = customer_id
        self.table_id = table_id
        self.start_at = start_at
        self.guests = guests
        self.status = status


class Order(Entity):
    def __init__(self, id, reservation_id, waiter_id, created_at, status="Открыт"):
        check_id(id)
        check_id(reservation_id, "ID брони")
        check_id(waiter_id, "ID официанта")
        if status not in ORDER_STATUSES:
            raise ValidationError("Статус заказа: Открыт, Оплачен или Отменён.")
        check_date(created_at, "%Y-%m-%d %H:%M",
                   "Дата заказа должна быть в формате ГГГГ-ММ-ДД ЧЧ:ММ.")
        self.id = id
        self.reservation_id = reservation_id
        self.waiter_id = waiter_id
        self.created_at = created_at
        self.status = status


class OrderItem(Entity):
    def __init__(self, id, order_id, dish_id, quantity):
        check_id(id)
        check_id(order_id, "ID заказа")
        check_id(dish_id, "ID блюда")
        check_id(quantity, "Количество порций")
        self.id = id
        self.order_id = order_id
        self.dish_id = dish_id
        self.quantity = quantity


# ---------------------------------------------------------------------------
# Таблицы для загрузки и сохранения.
# Порядок важен: сначала то, на что потом ссылаются другие объекты.
# ---------------------------------------------------------------------------

KEYS = ["categories", "menus", "halls", "tables", "customers", "waiters", "shifts",
        "products", "dishes", "ingredients", "reservations", "orders", "order_items"]

# ключ -> класс
CLASSES = {
    "categories": DishCategory, "menus": Menu, "halls": Hall, "tables": Table,
    "customers": Customer, "waiters": Waiter, "shifts": Shift, "products": Product,
    "dishes": Dish, "ingredients": DishIngredient, "reservations": Reservation,
    "orders": Order, "order_items": OrderItem,
}

# ключ -> имя метода добавления в Restaurant
ADD_METHODS = {
    "categories": "add_category", "menus": "add_menu", "halls": "add_hall",
    "tables": "add_table", "customers": "add_customer", "waiters": "add_waiter",
    "shifts": "add_shift", "products": "add_product", "dishes": "add_dish",
    "ingredients": "add_ingredient", "reservations": "add_reservation",
    "orders": "add_order", "order_items": "add_order_item",
}

# ключ -> тег одного элемента в XML
XML_TAGS = {
    "categories": "category", "menus": "menu", "halls": "hall", "tables": "table",
    "customers": "customer", "waiters": "waiter", "shifts": "shift",
    "products": "product", "dishes": "dish", "ingredients": "ingredient",
    "reservations": "reservation", "orders": "order", "order_items": "order_item",
}

# В XML всё хранится текстом, поэтому типы полей возвращаем по этим спискам
INT_FIELDS = ["id", "hall_id", "number", "seats", "waiter_id", "menu_id", "category_id",
              "dish_id", "product_id", "customer_id", "table_id", "guests",
              "reservation_id", "order_id", "quantity"]
FLOAT_FIELDS = ["price", "stock", "amount"]


# ---------------------------------------------------------------------------
# 4. Главный класс Restaurant: хранит все списки и работает с ними
# ---------------------------------------------------------------------------

class Restaurant:
    def __init__(self, name):
        self.name = check_text(name, "Название ресторана")
        self.categories = []
        self.menus = []
        self.halls = []
        self.tables = []
        self.customers = []
        self.waiters = []
        self.shifts = []
        self.products = []
        self.dishes = []
        self.ingredients = []
        self.reservations = []
        self.orders = []
        self.order_items = []

    # ----- общие методы -----

    def find_by_id(self, items, item_id, what):
        """Ищет объект в списке по ID."""
        check_id(item_id)
        for item in items:
            if item.id == item_id:
                return item
        raise EntityNotFoundError(what + " с ID " + str(item_id) + " не найден(а).")

    def add_to_list(self, items, new_item):
        """Добавляет объект, если такого ID ещё нет."""
        for item in items:
            if item.id == new_item.id:
                raise DuplicateEntityError("Сущность с ID " + str(new_item.id) + " уже существует.")
        items.append(new_item)

    # ----- добавление (перед этим проверяем, что связанные объекты есть) -----

    def add_category(self, item):
        self.add_to_list(self.categories, item)

    def add_menu(self, item):
        self.add_to_list(self.menus, item)

    def add_hall(self, item):
        self.add_to_list(self.halls, item)

    def add_table(self, item):
        self.find_by_id(self.halls, item.hall_id, "Зал")
        # номер столика не должен повторяться в одном зале
        for t in self.tables:
            if t.hall_id == item.hall_id and t.number == item.number:
                raise DuplicateEntityError("Столик №" + str(item.number) + " уже есть в этом зале.")
        self.add_to_list(self.tables, item)

    def add_customer(self, item):
        self.add_to_list(self.customers, item)

    def add_waiter(self, item):
        self.find_by_id(self.halls, item.hall_id, "Зал")
        self.add_to_list(self.waiters, item)

    def add_shift(self, item):
        self.find_by_id(self.waiters, item.waiter_id, "Официант")
        self.add_to_list(self.shifts, item)

    def add_product(self, item):
        self.add_to_list(self.products, item)

    def add_dish(self, item):
        self.find_by_id(self.menus, item.menu_id, "Меню")
        self.find_by_id(self.categories, item.category_id, "Категория")
        self.add_to_list(self.dishes, item)

    def add_ingredient(self, item):
        self.find_by_id(self.dishes, item.dish_id, "Блюдо")
        self.find_by_id(self.products, item.product_id, "Продукт")
        self.add_to_list(self.ingredients, item)

    def add_reservation(self, item):
        self.find_by_id(self.customers, item.customer_id, "Клиент")
        table = self.find_by_id(self.tables, item.table_id, "Столик")
        # гостей не может быть больше, чем мест
        if item.guests > table.seats:
            raise ValidationError("За столиком " + str(table.seats) + " мест, а гостей " + str(item.guests) + ".")
        # один столик нельзя занять дважды на одно время
        if item.status == "Запланирована":
            for r in self.reservations:
                if (r.table_id == item.table_id and r.start_at == item.start_at
                        and r.status == "Запланирована"):
                    raise ValidationError("Этот столик уже забронирован на указанное время.")
        self.add_to_list(self.reservations, item)

    def add_order(self, item):
        self.find_by_id(self.reservations, item.reservation_id, "Бронь")
        self.find_by_id(self.waiters, item.waiter_id, "Официант")
        self.add_to_list(self.orders, item)

    def add_order_item(self, item):
        order = self.find_by_id(self.orders, item.order_id, "Заказ")
        if order.status != "Открыт":
            raise ValidationError("Нельзя менять позиции закрытого заказа.")
        self.find_by_id(self.dishes, item.dish_id, "Блюдо")
        self.add_to_list(self.order_items, item)

    # ----- поиск -----

    def find_customer(self, customer_id):
        return self.find_by_id(self.customers, customer_id, "Клиент")

    def find_waiter(self, waiter_id):
        return self.find_by_id(self.waiters, waiter_id, "Официант")

    def find_table(self, table_id):
        return self.find_by_id(self.tables, table_id, "Столик")

    def find_dish(self, dish_id):
        return self.find_by_id(self.dishes, dish_id, "Блюдо")

    def find_reservation(self, reservation_id):
        return self.find_by_id(self.reservations, reservation_id, "Бронь")

    def find_order(self, order_id):
        return self.find_by_id(self.orders, order_id, "Заказ")

    # ----- изменение -----

    def update_customer(self, customer_id, full_name, phone, loyalty_card=""):
        old = self.find_customer(customer_id)
        # сначала создаём новый объект: так данные проверятся
        new = Customer(customer_id, full_name, phone, loyalty_card)
        old.full_name = new.full_name
        old.phone = new.phone
        old.loyalty_card = new.loyalty_card
        return old

    def update_dish_price(self, dish_id, price):
        dish = self.find_dish(dish_id)
        dish.price = check_number(price, "Цена блюда")

    def update_reservation_status(self, reservation_id, status):
        if status not in RESERVATION_STATUSES:
            raise ValidationError("Недопустимый статус брони.")
        self.find_reservation(reservation_id).status = status

    def update_order_status(self, order_id, status):
        if status not in ORDER_STATUSES:
            raise ValidationError("Недопустимый статус заказа.")
        self.find_order(order_id).status = status

    # ----- удаление (если на объект есть ссылки, удалять нельзя) -----

    def delete_customer(self, customer_id):
        customer = self.find_customer(customer_id)
        for r in self.reservations:
            if r.customer_id == customer_id:
                raise ValidationError("Нельзя удалить клиента, у которого есть брони.")
        self.customers.remove(customer)

    def delete_waiter(self, waiter_id):
        waiter = self.find_waiter(waiter_id)
        for o in self.orders:
            if o.waiter_id == waiter_id:
                raise ValidationError("Нельзя удалить официанта, у которого есть заказы.")
        for s in self.shifts:
            if s.waiter_id == waiter_id:
                raise ValidationError("Сначала удалите смены официанта.")
        self.waiters.remove(waiter)

    def delete_dish(self, dish_id):
        dish = self.find_dish(dish_id)
        for i in self.order_items:
            if i.dish_id == dish_id:
                raise ValidationError("Нельзя удалить блюдо, которое есть в заказах.")
        for i in self.ingredients:
            if i.dish_id == dish_id:
                raise ValidationError("Сначала удалите состав блюда.")
        self.dishes.remove(dish)

    def delete_reservation(self, reservation_id):
        reservation = self.find_reservation(reservation_id)
        for o in self.orders:
            if o.reservation_id == reservation_id:
                raise ValidationError("Нельзя удалить бронь, по которой есть заказ.")
        self.reservations.remove(reservation)

    # ----- подсчёты -----

    def order_total(self, order_id):
        """Сумма заказа: цена блюда * количество порций по каждой позиции."""
        self.find_order(order_id)
        total = 0
        for item in self.order_items:
            if item.order_id == order_id:
                total += self.find_dish(item.dish_id).price * item.quantity
        return total

    def dishes_by_menu(self, menu_id):
        """Список блюд одного меню."""
        self.find_by_id(self.menus, menu_id, "Меню")
        result = []
        for dish in self.dishes:
            if dish.menu_id == menu_id:
                result.append(dish)
        return result

    # ----- превращение в словарь и обратно -----

    def to_dict(self):
        data = {"restaurant": self.name}
        for key in KEYS:
            data[key] = []
            for item in getattr(self, key):
                data[key].append(item.to_dict())
        return data

    @classmethod
    def from_dict(cls, data):
        try:
            restaurant = cls(data["restaurant"])
            for key in KEYS:
                add_method = getattr(restaurant, ADD_METHODS[key])
                for raw in data[key]:
                    add_method(CLASSES[key](**raw))
            return restaurant
        except KeyError as e:
            raise ValidationError("В файле отсутствует обязательное поле: " + str(e) + ".")
        except TypeError as e:
            raise ValidationError("Структура данных не соответствует модели: " + str(e) + ".")

    # ----- JSON -----

    def save_json(self, filename):
        try:
            folder = os.path.dirname(filename)
            if folder != "":
                os.makedirs(folder, exist_ok=True)  # создаём папку, если её нет
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        except (OSError, TypeError, ValueError) as e:
            raise StorageError("Не удалось записать JSON-файл: " + str(e))

    @classmethod
    def load_json(cls, filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValidationError("Корень JSON должен быть объектом.")
            return cls.from_dict(data)
        except FileNotFoundError:
            raise StorageError("JSON-файл не найден: " + str(filename))
        except json.JSONDecodeError as e:
            raise StorageError("Ошибка синтаксиса JSON, строка " + str(e.lineno) + ": " + e.msg)
        except OSError as e:
            raise StorageError("Не удалось прочитать JSON: " + str(e))

    # ----- XML -----

    def save_xml(self, filename):
        try:
            root = ET.Element("restaurant", {"name": self.name})
            data = self.to_dict()
            for key in KEYS:
                group = ET.SubElement(root, key)  # например <dishes>
                for row in data[key]:
                    element = ET.SubElement(group, XML_TAGS[key])  # например <dish>
                    for field_name in row:
                        child = ET.SubElement(element, field_name)
                        child.text = str(row[field_name])
            ET.indent(root, space="  ")
            folder = os.path.dirname(filename)
            if folder != "":
                os.makedirs(folder, exist_ok=True)
            ET.ElementTree(root).write(filename, encoding="utf-8", xml_declaration=True)
        except (OSError, TypeError, ValueError) as e:
            raise StorageError("Не удалось записать XML-файл: " + str(e))

    @classmethod
    def load_xml(cls, filename):
        try:
            root = ET.parse(filename).getroot()
            data = {"restaurant": root.attrib["name"]}
            for key in KEYS:
                data[key] = []
                group = root.find(key)
                if group is None:
                    continue
                for element in group:
                    row = {}
                    for child in element:
                        text = child.text or ""
                        # возвращаем нужный тип, т.к. из XML всё приходит строкой
                        if child.tag in INT_FIELDS:
                            row[child.tag] = int(text)
                        elif child.tag in FLOAT_FIELDS:
                            row[child.tag] = float(text)
                        else:
                            row[child.tag] = text
                    data[key].append(row)
            return cls.from_dict(data)
        except FileNotFoundError:
            raise StorageError("XML-файл не найден: " + str(filename))
        except ET.ParseError as e:
            raise StorageError("Некорректный XML: " + str(e))
        except (KeyError, OSError, ValueError) as e:
            raise StorageError("Не удалось прочитать XML: " + str(e))


# ---------------------------------------------------------------------------
# 5. Демо-данные и вывод на экран
# ---------------------------------------------------------------------------

def create_demo_restaurant():
    r = Restaurant("Ресторан «Лаборатория вкуса»")

    # справочники
    r.add_category(DishCategory(1, "Салаты", "Холодные закуски"))
    r.add_category(DishCategory(2, "Горячее", "Основные блюда"))
    r.add_menu(Menu(1, "Основное меню", "Постоянное меню ресторана"))
    r.add_hall(Hall(1, "Основной зал", "1 этаж"))
    r.add_hall(Hall(2, "Летняя веранда", "Терраса"))

    # столики, клиенты, официанты и смены
    r.add_table(Table(1, 1, 1, 4))
    r.add_table(Table(2, 1, 2, 2))
    r.add_table(Table(3, 2, 1, 6))
    r.add_customer(Customer(1, "Монин Арсений Артемович", "+7-900-111-22-33", "CARD-001"))
    r.add_customer(Customer(2, "Спиридонов Артем Федотович", "+7-900-222-33-44"))
    r.add_waiter(Waiter(1, " Тарасов Арсений Валентинович", 1, "Старший официант"))
    r.add_waiter(Waiter(2, "Малуси  Ндаба Эниинная", 2, "Официант"))
    r.add_shift(Shift(1, 1, "Пн–Пт", "10:00", "18:00"))
    r.add_shift(Shift(2, 2, "Сб–Вс", "12:00", "22:00"))

    # продукты, блюда и состав блюд
    r.add_product(Product(1, "Говядина", "кг", 25.0))
    r.add_product(Product(2, "Картофель", "кг", 40.0))
    r.add_product(Product(3, "Томаты", "кг", 15.0))
    r.add_dish(Dish(1, "Стейк с картофелем", 1500.0, 1, 2, "Говяжий стейк на гриле"))
    r.add_dish(Dish(2, "Салат с томатами", 450.0, 1, 1))
    r.add_ingredient(DishIngredient(1, 1, 1, 0.25))
    r.add_ingredient(DishIngredient(2, 1, 2, 0.20))
    r.add_ingredient(DishIngredient(3, 2, 3, 0.15))

    # брони, заказ и его позиции
    r.add_reservation(Reservation(1, 1, 1, "2026-11-02 19:00", 3))
    r.add_reservation(Reservation(2, 2, 3, "2026-11-02 20:00", 5))
    r.add_order(Order(1, 1, 1, "2026-11-02 19:10"))
    r.add_order_item(OrderItem(1, 1, 1, 2))
    r.add_order_item(OrderItem(2, 1, 2, 1))
    return r


def print_summary(restaurant):
    print("\n" + restaurant.name)
    print("Залов:", len(restaurant.halls), "| Столиков:", len(restaurant.tables),
          "| Меню:", len(restaurant.menus))
    print("Клиентов:", len(restaurant.customers), "| Официантов:", len(restaurant.waiters),
          "| Смен:", len(restaurant.shifts))
    print("Блюд:", len(restaurant.dishes), "| Продуктов:", len(restaurant.products),
          "| Броней:", len(restaurant.reservations))

    for res in restaurant.reservations:
        customer = restaurant.find_customer(res.customer_id)
        table = restaurant.find_table(res.table_id)
        print("  Бронь #" + str(res.id) + ": " + res.start_at + " — " + customer.full_name
              + "; столик №" + str(table.number) + "; гостей: " + str(res.guests)
              + "; " + res.status)

    for order in restaurant.orders:
        waiter = restaurant.find_waiter(order.waiter_id)
        total = restaurant.order_total(order.id)
        print("  Заказ #" + str(order.id) + ": официант " + waiter.full_name
              + "; сумма " + format(total, ".2f") + " руб.; " + order.status)


# ---------------------------------------------------------------------------
# 6. Запуск
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Учёт ресторана (ЛР1)")
    parser.add_argument("--demo", action="store_true",
                        help="создать демонстрационные данные и сохранить JSON/XML")
    parser.add_argument("--data", default="data",
                        help="папка для файлов данных (по умолчанию data)")
    args = parser.parse_args()

    json_path = os.path.join(args.data, "restaurant.json")
    xml_path = os.path.join(args.data, "restaurant.xml")

    try:
        if args.demo:
            restaurant = create_demo_restaurant()
            restaurant.save_json(json_path)
            restaurant.save_xml(xml_path)
            print("Демонстрационные данные созданы и сохранены в JSON и XML.")
        else:
            if os.path.exists(json_path):
                restaurant = Restaurant.load_json(json_path)
            else:
                restaurant = create_demo_restaurant()
                print("Файл данных пока отсутствует; показаны демонстрационные данные.")
        print_summary(restaurant)
        return 0
    except RestaurantError as e:
        print("Ошибка предметной области: " + str(e), file=sys.stderr)
        return 1
    except (ValueError, TypeError) as e:
        print("Ошибка входных данных: " + str(e), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nРабота прервана пользователем.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
