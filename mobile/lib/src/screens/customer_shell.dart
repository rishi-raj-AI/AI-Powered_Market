import 'package:flutter/material.dart';
import 'market_screen.dart';
import 'cart_screen.dart';
import 'orders_screen.dart';
import 'notifications_screen.dart';

class CustomerShell extends StatefulWidget {
  final VoidCallback onLogout;
  const CustomerShell({super.key, required this.onLogout});
  @override
  State<CustomerShell> createState() => _CustomerShellState();
}

class _CustomerShellState extends State<CustomerShell> {
  int index = 0;
  @override
  Widget build(BuildContext context) {
    final pages = [
      MarketScreen(onLoggedOut: widget.onLogout),
      const CartScreen(),
      const OrdersScreen(),
      const NotificationsScreen(),
    ];
    return Scaffold(
      body: IndexedStack(index: index, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) => setState(() => index = value),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.storefront_outlined), selectedIcon: Icon(Icons.storefront), label: 'Market'),
          NavigationDestination(icon: Icon(Icons.shopping_cart_outlined), selectedIcon: Icon(Icons.shopping_cart), label: 'Cart'),
          NavigationDestination(icon: Icon(Icons.receipt_long_outlined), selectedIcon: Icon(Icons.receipt_long), label: 'Orders'),
          NavigationDestination(icon: Icon(Icons.notifications_none), selectedIcon: Icon(Icons.notifications), label: 'Updates'),
        ],
      ),
    );
  }
}
