let idToken = "";
let oauthClientId = "";
let authMode = "local";

const signinPanel = document.querySelector("#signin-panel");
const uploadForm = document.querySelector("#upload-form");
const fileInput = document.querySelector("#scan");
const submitButton = document.querySelector("#submit");
const message = document.querySelector("#message");
const previewWrap = document.querySelector("#preview-wrap");
const preview = document.querySelector("#preview");
const localSignin = document.querySelector("#local-signin");
const accessKeyInput = document.querySelector("#access-key");

fetch("/api/config")
  .then((response) => response.json())
  .then((config) => {
    authMode = config.authMode;
    oauthClientId = config.googleOAuthClientId;
    initializeAuthentication();
  })
  .catch(() => showMessage("Could not load uploader configuration.", "error"));

function initializeAuthentication() {
  if (authMode === "local") {
    localSignin.hidden = false;
    document.querySelector("#google-signin").hidden = true;
    const savedKey = window.localStorage.getItem("personal-os-upload-key");
    if (savedKey) unlockLocalUploader(savedKey);
    return;
  }

  document.querySelector("#auth-title").textContent = "Sign in to continue";
  document.querySelector("#auth-help").textContent = "Only your approved Google account can upload.";
  loadGoogleSignIn();
}

function loadGoogleSignIn() {
  if (window.google?.accounts?.id) return initializeGoogleSignIn();
  const script = document.createElement("script");
  script.src = "https://accounts.google.com/gsi/client";
  script.async = true;
  script.onload = initializeGoogleSignIn;
  document.head.appendChild(script);
}

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

localSignin.addEventListener("submit", (event) => {
  event.preventDefault();
  const key = accessKeyInput.value.trim();
  if (!key) return;
  window.localStorage.setItem("personal-os-upload-key", key);
  unlockLocalUploader(key);
});

function unlockLocalUploader(key) {
  idToken = key;
  document.querySelector("#account-label").textContent = "Private device";
  signinPanel.hidden = true;
  uploadForm.hidden = false;
  clearMessage();
}

document.querySelector("#signout").addEventListener("click", () => {
  idToken = "";
  if (authMode === "local") {
    window.localStorage.removeItem("personal-os-upload-key");
    accessKeyInput.value = "";
  } else {
    google.accounts.id.disableAutoSelect();
  }
  uploadForm.hidden = true;
  signinPanel.hidden = false;
  fileInput.value = "";
  resetSelection();
});

fileInput.addEventListener("change", () => {
  const files = Array.from(fileInput.files);
  if (!files.length) return resetSelection();

  const totalSize = files.reduce((sum, file) => sum + file.size, 0);
  const oversized = files.find((file) => file.size > 20 * 1024 * 1024);
  if (files.length > 10 || oversized || totalSize > 100 * 1024 * 1024) {
    const problem = files.length > 10
      ? "Choose no more than 10 files."
      : oversized
        ? `${oversized.name} is larger than 20 MB.`
        : "The selected files are larger than 100 MB in total.";
    fileInput.value = "";
    resetSelection();
    showMessage(problem, "error");
    return;
  }

  const file = files[0];
  document.querySelector("#file-title").textContent = files.length === 1
    ? file.name
    : `${files.length} files selected`;
  document.querySelector("#file-detail").textContent = `${formatBytes(totalSize)} total`;
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
  const files = Array.from(fileInput.files);
  if (!files.length || !idToken) return;

  submitButton.disabled = true;
  submitButton.querySelector("span:first-child").textContent = "Uploading…";
  clearMessage();
  const form = new FormData();
  files.forEach((file) => form.append("file", file));

  try {
    const response = await fetch("/api/notes", {
      method: "POST",
      headers: { Authorization: `Bearer ${idToken}` },
      body: form,
    });
    const body = await response.json();
    if (response.status === 401 || response.status === 403) {
      window.localStorage.removeItem("personal-os-upload-key");
      idToken = "";
      uploadForm.hidden = true;
      signinPanel.hidden = false;
    }
    if (!response.ok) throw new Error(body.detail || "Upload failed");
    const noun = body.count === 1 ? "note" : "notes";
    showMessage(`Saved ${body.count} ${noun} privately.`, "success");
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
  document.querySelector("#file-title").textContent = "Take photos or choose files";
  document.querySelector("#file-detail").textContent = "Up to 10 files · 20 MB each · 100 MB total";
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
