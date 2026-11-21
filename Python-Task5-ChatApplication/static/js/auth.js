// Small helpers for the login / register pages.
(function () {
  document.querySelectorAll(".pw-toggle").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = document.getElementById(btn.dataset.target);
      var showing = input.type === "text";
      input.type = showing ? "password" : "text";
      btn.textContent = showing ? "Show" : "Hide";
      btn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
    });
  });

  // Password strength meter (register page only).
  var pw = document.getElementById("pw");
  var meter = document.querySelector(".meter i");
  var hint = document.getElementById("pw-hint");
  var confirmBox = document.getElementById("confirm");
  if (pw && meter) {
    pw.addEventListener("input", function () {
      var v = pw.value, score = 0;
      if (v.length >= 8) score++;
      if (v.length >= 12) score++;
      if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score++;
      if (/\d/.test(v) && /[^A-Za-z0-9]/.test(v)) score++;
      var labels = ["Too short", "Weak", "Okay", "Good", "Strong"];
      var colors = ["#ff6b6b", "#ff8a6b", "#f5c542", "#6bdc9a", "#22d3c5"];
      meter.style.width = (v ? (score + 1) * 20 : 0) + "%";
      meter.style.background = colors[score];
      if (hint) hint.textContent = v ? labels[score] : "At least 8 characters.";
    });
  }
  if (confirmBox && pw) {
    confirmBox.addEventListener("input", function () {
      confirmBox.classList.toggle("mismatch", confirmBox.value !== "" && confirmBox.value !== pw.value);
    });
  }
})();
