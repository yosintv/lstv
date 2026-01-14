function generatePassword() {
  const length = document.getElementById("length").value;
  const symbols = document.getElementById("symbols")?.checked ?? true;

  let chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  if (symbols) chars += "!@#$%^&*()_+";

  let pass = "";
  for (let i = 0; i < length; i++) {
    pass += chars.charAt(Math.floor(Math.random() * chars.length));
  }

  document.getElementById("output").value = pass;
}
