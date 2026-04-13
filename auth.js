import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
} from "https://www.gstatic.com/firebasejs/12.12.0/firebase-auth.js";
import { get, onValue, ref, set } from "https://www.gstatic.com/firebasejs/12.12.0/firebase-database.js";
import { auth, database } from "./firebase.js";

const PLATFORM_USERS_PATH = "platform/users";

function toRecordMap(items) {
  const result = {};
  (Array.isArray(items) ? items : []).forEach((item) => {
    const id = String(item?.id || "").trim();
    if (id) result[id] = item;
  });
  return result;
}

function fromRecordMap(recordMap) {
  return Object.values(recordMap || {}).filter(Boolean);
}

function getFirebaseErrorCode(error) {
  const directCode = String(error?.code || "").trim().toLowerCase();
  const serverMessage = String(
    error?.customData?._serverResponse ||
    error?.customData?._tokenResponse?.error?.message ||
    error?.customData?._tokenResponse?.message ||
    "",
  ).toUpperCase();
  const message = String(error?.message || "").toUpperCase();
  const details = `${serverMessage} ${message}`;

  if (details.includes("CONFIGURATION_NOT_FOUND")) return "auth/configuration-not-found";
  if (details.includes("OPERATION_NOT_ALLOWED")) return "auth/operation-not-allowed";
  if (details.includes("EMAIL_EXISTS")) return "auth/email-already-in-use";
  if (details.includes("INVALID_LOGIN_CREDENTIALS")) return "auth/invalid-credential";
  if (details.includes("INVALID_PASSWORD")) return "auth/wrong-password";
  if (details.includes("EMAIL_NOT_FOUND")) return "auth/user-not-found";
  if (details.includes("WEAK_PASSWORD")) return "auth/weak-password";
  if (details.includes("UNAUTHORIZED_DOMAIN")) return "auth/unauthorized-domain";

  return directCode;
}

function getFirebaseErrorMessage(error) {
  switch (getFirebaseErrorCode(error)) {
    case "auth/email-already-in-use":
      return "هذا البريد مسجل بالفعل";
    case "auth/invalid-email":
      return "صيغة البريد الإلكتروني غير صحيحة";
    case "auth/weak-password":
      return "كلمة السر ضعيفة، استخدم 6 أحرف على الأقل";
    case "auth/missing-password":
      return "كلمة السر مطلوبة";
    case "auth/user-not-found":
    case "auth/wrong-password":
    case "auth/invalid-credential":
      return "البريد أو كلمة السر غير صحيحة";
    case "auth/network-request-failed":
      return "تعذر الاتصال بخدمة Firebase حالياً";
    case "auth/too-many-requests":
      return "تم تجاوز عدد المحاولات، حاول لاحقاً";
    case "auth/configuration-not-found":
    case "auth/operation-not-allowed":
      return "مصادقة البريد الإلكتروني غير مفعلة في مشروع Firebase حالياً";
    case "auth/unauthorized-domain":
      return "النطاق الحالي غير مسموح به داخل إعدادات Firebase Authentication";
    default:
      return error?.message || "حدث خطأ غير متوقع في Firebase";
  }
}

function shouldUseLocalAuthFallback(error) {
  return [
    "auth/configuration-not-found",
    "auth/operation-not-allowed",
    "auth/unauthorized-domain",
    "auth/operation-not-supported-in-this-environment",
  ].includes(getFirebaseErrorCode(error));
}

const bridge = {
  ready: true,
  auth,
  database,
  register(email, password) {
    return createUserWithEmailAndPassword(auth, email, password);
  },
  login(email, password) {
    return signInWithEmailAndPassword(auth, email, password);
  },
  logout() {
    return signOut(auth);
  },
  onAuthStateChanged(callback) {
    return onAuthStateChanged(auth, callback);
  },
  async loadPlatformUsers() {
    const snapshot = await get(ref(database, PLATFORM_USERS_PATH));
    const value = snapshot.exists() ? snapshot.val() : {};
    return {
      students: fromRecordMap(value.students),
      teachers: fromRecordMap(value.teachers),
    };
  },
  savePlatformUsers({ students, teachers }) {
    return set(ref(database, PLATFORM_USERS_PATH), {
      students: toRecordMap(students),
      teachers: toRecordMap(teachers),
    });
  },
  subscribePlatformUsers(callback, onError) {
    return onValue(
      ref(database, PLATFORM_USERS_PATH),
      (snapshot) => {
        const value = snapshot.exists() ? snapshot.val() : {};
        callback({
          students: fromRecordMap(value.students),
          teachers: fromRecordMap(value.teachers),
        });
      },
      onError,
    );
  },
  getErrorMessage(error) {
    return getFirebaseErrorMessage(error);
  },
  getErrorCode(error) {
    return getFirebaseErrorCode(error);
  },
  shouldUseLocalAuthFallback(error) {
    return shouldUseLocalAuthFallback(error);
  },
};

window.minasatAuth = bridge;
window.dispatchEvent(new CustomEvent("minasat-auth-ready"));

export { bridge, getFirebaseErrorCode, getFirebaseErrorMessage, shouldUseLocalAuthFallback };