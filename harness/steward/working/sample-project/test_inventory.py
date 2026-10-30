import unittest

from inventory import Item, low_stock, order_total


class OrderTotalTests(unittest.TestCase):
    def test_no_discount(self):
        items = [Item("bolt", 0.25, 40), Item("nut", 0.10, 40)]
        self.assertEqual(order_total(items), 14.0)

    def test_zero_discount(self):
        items = [Item("bolt", 0.25, 40), Item("nut", 0.10, 40)]
        self.assertEqual(order_total(items, discount_percent=0), 14.0)

    def test_percent_discount(self):
        items = [Item("drill", 80.0, 1), Item("bit set", 20.0, 1)]
        self.assertEqual(order_total(items, discount_percent=10), 90.0)


class LowStockTests(unittest.TestCase):
    def test_threshold_is_inclusive(self):
        items = [Item("saw", 30.0, 5), Item("tape", 4.0, 6)]
        self.assertEqual(low_stock(items), ["saw"])


if __name__ == "__main__":
    unittest.main()
