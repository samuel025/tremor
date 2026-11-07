import { defineConfig } from "vite";
export default defineConfig({ base: "./", define: { "process.env": {} }, build: { target: "es2022" } });
