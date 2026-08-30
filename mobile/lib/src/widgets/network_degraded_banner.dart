import 'package:flutter/material.dart';

import '../offline/offline_support.dart';

class NetworkDegradedBanner extends StatelessWidget {
  final Widget child;
  const NetworkDegradedBanner({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<bool>(
      valueListenable: OfflineSupport.degraded,
      builder: (context, degraded, _) {
        return Stack(
          children: [
            child,
            if (degraded)
              Positioned(
                left: 0,
                right: 0,
                top: 0,
                child: SafeArea(
                  bottom: false,
                  child: Material(
                    elevation: 2,
                    child: InkWell(
                      onTap: OfflineSupport.flushTelemetry,
                      child: const Padding(
                        padding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.cloud_off_outlined, size: 18),
                            SizedBox(width: 8),
                            Flexible(child: Text('Weak connection • saved data may be shown • tap to retry sync', textAlign: TextAlign.center)),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}
