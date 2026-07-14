function useMyLocation(latFieldId, lngFieldId, statusId) {
  const status = document.getElementById(statusId);
  if (!navigator.geolocation) {
    if (status) status.textContent = "Geolocation not supported on this browser.";
    return;
  }
  if (status) status.textContent = "Locating...";
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      document.getElementById(latFieldId).value = pos.coords.latitude.toFixed(6);
      document.getElementById(lngFieldId).value = pos.coords.longitude.toFixed(6);
      if (status) status.textContent = "Location captured ✓";
    },
    (err) => {
      if (status) status.textContent = "Couldn't get location -- you can enter an address instead.";
    }
  );
}

// Auto-dismiss flash messages after a few seconds
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".flash").forEach((el) => {
    setTimeout(() => { el.style.transition = "opacity 0.5s"; el.style.opacity = "0"; }, 4000);
  });
});
