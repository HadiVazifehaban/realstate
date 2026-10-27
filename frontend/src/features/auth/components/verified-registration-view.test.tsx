import * as React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

const { signIn } = vi.hoisted(() => ({ signIn: vi.fn() }));
vi.mock("./keycloak-sign-in", () => ({ beginKeycloakSignIn: signIn }));
import { generateSecurePassword, VerifiedRegistrationView } from "./verified-registration-view";

function fillPasswords() {
  fireEvent.change(screen.getByLabelText("رمز عبور", { exact: true }), { target: { value: "SecurePass12!" } });
  fireEvent.change(screen.getByLabelText("تکرار رمز عبور"), { target: { value: "SecurePass12!" } });
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.clearAllMocks(); });

it("keeps the decorative background out of the accessibility tree and identifies the active step", () => {
  const { container } = render(<VerifiedRegistrationView />);
  expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull();
  expect(screen.getByRole("list", { name: "مراحل ثبت‌نام" }).querySelector('[aria-current="step"]')?.textContent).toContain("اطلاعات شما");
  expect(screen.getByRole("link", { name: /شکارچی/ }).getAttribute("href")).toBe("/");
  const brand = screen.getByRole("link", { name: /شکارچی/ });
  expect(brand.querySelector('img')?.getAttribute('src')).toMatch(/^\/brand\/logo(?:-light|-dark)?\.png\?v=/);
  expect(brand.querySelector('img')?.getAttribute('alt')).toBe('لوگوی سامانه شکارچی');
  expect(brand.querySelector('[class*="brandMark"]')).toBeNull();
});

it("shows registration without redirecting to login and only creates after OTP verification", async () => {
  const fetch = vi.fn()
    .mockResolvedValueOnce(Response.json({ ok: true }))
    .mockResolvedValueOnce(Response.json({ ok: true, registration_token: "verified-proof" }))
    .mockResolvedValueOnce(Response.json({ ok: true, username: "my.username" }));
  vi.stubGlobal("fetch", fetch);
  render(<VerifiedRegistrationView />);
  expect(signIn).not.toHaveBeenCalled();
  for (const [label, value] of [["نام", "نام"], ["نام خانوادگی", "خانوادگی"],
    ["نام کاربری دلخواه", "my.username"], ["شماره موبایل", "09120000001"]]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
  fillPasswords();
  fireEvent.click(screen.getByRole("button", { name: "دریافت کد تأیید" }));
  await screen.findByLabelText("کد تأیید پیامکی");
  expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText("کد تأیید پیامکی"), { target: { value: "۱۲۳۴۵۶" } });
  fireEvent.click(screen.getByRole("button", { name: "تأیید کد و ساخت حساب" }));
  await screen.findByRole("status");
  expect(JSON.parse(fetch.mock.calls[1][1].body).otp_code).toBe("123456");
  expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({
    registration_token: "verified-proof", username: "my.username", first_name: "نام", last_name: "خانوادگی", password: "SecurePass12!"
  });
  expect(signIn).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "ورود به حساب" }));
  await waitFor(() => expect(signIn).toHaveBeenCalledWith({ loginHint: "my.username" }));
});

it("never creates an account when OTP is wrong", async () => {
  const fetch = vi.fn().mockResolvedValueOnce(Response.json({ ok: true }))
    .mockResolvedValueOnce(Response.json({ detail: { message: "کد نامعتبر است" } }, { status: 400 }));
  vi.stubGlobal("fetch", fetch);
  render(<VerifiedRegistrationView />);
  fillPasswords();
  fireEvent.submit(screen.getByRole("button", { name: "دریافت کد تأیید" }).closest("form")!);
  await screen.findByLabelText("کد تأیید پیامکی");
  fireEvent.submit(screen.getByRole("button", { name: "تأیید کد و ساخت حساب" }).closest("form")!);
  expect((await screen.findByRole("alert")).textContent).toBe("کد نامعتبر است");
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(signIn).not.toHaveBeenCalled();
});

it("shows a duplicate username error beside the field and preserves the entered identity", async () => {
  const message = "نام کاربری تکراری است؛ نام دیگری انتخاب کنید و دوباره کد تأیید بگیرید.";
  const fetch = vi.fn()
    .mockResolvedValueOnce(Response.json({ ok: true }))
    .mockResolvedValueOnce(Response.json({ ok: true, registration_token: "verified-proof" }))
    .mockResolvedValueOnce(Response.json({ detail: { error: "username_taken", message } }, { status: 409 }));
  vi.stubGlobal("fetch", fetch);
  render(<VerifiedRegistrationView />);
  fireEvent.change(screen.getByLabelText("نام کاربری دلخواه"), { target: { value: "taken.name" } });
  fireEvent.change(screen.getByLabelText("نام"), { target: { value: "نام" } });
  fillPasswords();
  fireEvent.submit(screen.getByRole("button", { name: "دریافت کد تأیید" }).closest("form")!);
  await screen.findByLabelText("کد تأیید پیامکی");
  fireEvent.change(screen.getByLabelText("کد تأیید پیامکی"), { target: { value: "123456" } });
  fireEvent.submit(screen.getByRole("button", { name: "تأیید کد و ساخت حساب" }).closest("form")!);
  expect((await screen.findByRole("alert")).textContent).toBe(message);
  const username = screen.getByLabelText("نام کاربری دلخواه") as HTMLInputElement;
  expect(username.value).toBe("taken.name");
  expect(username.getAttribute("aria-invalid")).toBe("true");
  expect(username.getAttribute("aria-describedby")).toContain("register-username-error");
  expect(document.getElementById("register-username-error")?.textContent).toBe(message);
  expect((screen.getByLabelText("نام") as HTMLInputElement).value).toBe("نام");
  expect(signIn).not.toHaveBeenCalled();
  fireEvent.change(username, { target: { value: "another.name" } });
  expect(username.hasAttribute("aria-invalid")).toBe(false);
  expect(screen.queryByRole("alert")).toBeNull();
});

it("associates the username field with a clear guide and a left-to-right example", () => {
  render(<VerifiedRegistrationView />);
  const username = screen.getByLabelText("نام کاربری دلخواه");
  expect(username.getAttribute("aria-describedby")).toBe("register-username-help");
  const help = document.getElementById("register-username-help")!;
  expect(help.textContent).toContain("بدون فاصله");
  expect(help.textContent).toContain("۳ تا ۶۴ کاراکتر");
  expect(help.querySelector('bdi[dir="ltr"]')?.textContent).toBe("ali.reza_123");
});

it("generates a 12-character password with all character groups and fills both fields", () => {
  for (let i = 0; i < 50; i++) {
    const value = generateSecurePassword();
    expect(value).toHaveLength(12);
    expect(value).toMatch(/[A-Z]/);
    expect(value).toMatch(/[a-z]/);
    expect(value).toMatch(/[0-9]/);
    expect(value).toMatch(/[^a-zA-Z0-9]/);
  }
  render(<VerifiedRegistrationView />);
  fireEvent.click(screen.getByRole("button", { name: "پیشنهاد رمز عبور امن" }));
  const password = screen.getByLabelText("رمز عبور", { exact: true }) as HTMLInputElement;
  expect(password.value).toHaveLength(12);
  expect((screen.getByLabelText("تکرار رمز عبور") as HTMLInputElement).value).toBe(password.value);
  expect(password.type).toBe("password");
  fireEvent.click(screen.getByRole("button", { name: "نمایش رمز عبور" }));
  expect(password.type).toBe("text");
});

it("rejects mismatched passwords before requesting any OTP", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  render(<VerifiedRegistrationView />);
  fillPasswords();
  fireEvent.change(screen.getByLabelText("تکرار رمز عبور"), { target: { value: "DifferentPass12!" } });
  fireEvent.submit(screen.getByRole("button", { name: "دریافت کد تأیید" }).closest("form")!);
  expect((await screen.findByRole("alert")).textContent).toContain("یکسان نیستند");
  expect(fetch).not.toHaveBeenCalled();
});