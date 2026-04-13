import { getApp, getApps, initializeApp } from "https://www.gstatic.com/firebasejs/12.12.0/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/12.12.0/firebase-auth.js";
import { getDatabase } from "https://www.gstatic.com/firebasejs/12.12.0/firebase-database.js";

const firebaseConfig = {
  apiKey: "AIzaSyCwjchJRPxlDawxxDeTaPLRU-ihie--SEY",
  authDomain: "minasatkisai.firebaseapp.com",
  databaseURL: "https://minasatkisai-default-rtdb.firebaseio.com",
  projectId: "minasatkisai",
  storageBucket: "minasatkisai.firebasestorage.app",
  messagingSenderId: "807884913188",
  appId: "1:807884913188:web:4c83fcafe910deef78b6b1",
  measurementId: "G-K542XECN5D"
};

const app = getApps().length ? getApp() : initializeApp(firebaseConfig);
const auth = getAuth(app);
const database = getDatabase(app);

export { app, auth, database, firebaseConfig };