/// The backend's last known GPS age is only current while polling succeeds.
/// After a failed poll, never advertise a cached route estimate as live.
bool isRiderLocationStale(Object? reportedAgeSeconds,
    {required bool connectionLost}) {
  if (connectionLost) return true;
  if (reportedAgeSeconds is! num ||
      !reportedAgeSeconds.isFinite ||
      reportedAgeSeconds < 0) {
    return true;
  }
  return reportedAgeSeconds > 30;
}
