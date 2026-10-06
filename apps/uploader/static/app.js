let idToken = "";
let oauthClientId = "";

const signinPanel = document.querySelector("#signin-panel");
const uploadForm = document.querySelector("#upload-form");
const fileInput = document.querySelector("#scan");
const submitButton = document.querySelector("#submit");
const message = document.querySelector("#message");
const previewWrap = document.querySelector("#preview-wrap");
const preview = document.querySelector("#preview");

fetch("/api/config")
  .then((response) => response.json())
  .then((config) => {
    oauthClientId = config.googleOAuthClientId;
    initializeGoogleSignIn();
  })
  .catch(() => showMessage("Could not load uploader configuration.", "error"));

window.addEventListener("load", initializeGoogleSignIn);

function initializeGoogleSignIn() {
  if (!oauthClientId || !window.google?.accounts?.id) return;
  google.accounts.id.initialize({
    client_id: oauthClientId,
    callback: handleCredential,
    auto_select: true,
  });
  google.accounts.id.renderButton(document.querySelector("#google-signin"), {
    type: "standard",
    theme: "outline",
    size: "large",
    shape: "rectangular",
    text: "continue_with",
    width: 280,
  });
}

function handleCredential(response) {
  idToken = response.credential;
  const claims = decodeClaims(idToken);
  document.querySelector("#account-label").textContent = claims.email || "Signed in";
  signinPanel.hidden = true;
  uploadForm.hidden = false;
  clearMessage();
}

document.querySelector("#signout").addEventListener("click", () => {
  idToken = "";
  google.accounts.id.disableAutoSelect();
  uploadForm.hidden = true;
  signinPanel.hidden = false;
  fileInput.value = "";
  resetSelection();
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (!file) return resetSelection();
  document.querySelector("#file-title").textContent = file.name;
  document.querySelector("#file-detail").textContent = formatBytes(file.size);
  submitButton.disabled = false;
  clearMessage();

  if (file.type.startsWith("image/") && file.type !== "image/heic" && file.type !== "image/heif") {
    preview.src = URL.createObjectURL(file);
    previewWrap.hidden = false;
  } else {
    previewWrap.hidden = true;
  }
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file || !idToken) return;

  submitButton.disabled = true;
  submitButton.querySelector("span:first-child").textContent = "Uploading…";
  clearMessage();
  const form = new FormData();
  form.append("file", file);

  try {
    const response = await fetch("/api/notes", {
      method: "POST",
      headers: { Authorization: `Bearer ${idToken}` },
      body: form,
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Upload failed");
    showMessage("Saved privately. Your note is ready for processing.", "success");
    fileInput.value = "";
    resetSelection();
  } catch (error) {
    showMessage(error.message || "Upload failed. Please try again.", "error");
    submitButton.disabled = false;
  } finally {
    submitButton.querySelector("span:first-child").textContent = "Upload note";
  }
});

function resetSelection() {
  document.querySelector("#file-title").textContent = "Take photo or choose file";
  document.querySelector("#file-detail").textContent = "JPEG, PNG, WebP, HEIC or PDF · up to 20 MB";
  previewWrap.hidden = true;
  preview.removeAttribute("src");
  submitButton.disabled = true;
}

function showMessage(text, kind) {
  message.textContent = text;
  message.className = `message ${kind}`;
  message.hidden = false;
}

function clearMessage() {
  message.hidden = true;
  message.textContent = "";
  message.className = "message";
}

function decodeClaims(token) {
  try {
    return JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
  } catch (_) {
    return {};
  }
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
