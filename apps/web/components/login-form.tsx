"use client";

import { useState } from "react";
import { ArrowRight, FlaskConical, LockKeyhole } from "lucide-react";
import type { Locale } from "@/lib/contracts";

interface LoginFormProps {
  locale: Locale;
  onLogin: (credentials: {
    email: string;
    password: string;
  }) => void | Promise<void>;
  onDemo: () => void | Promise<void>;
}

export function LoginForm({ locale, onLogin, onDemo }: LoginFormProps) {
  const ar = locale === "ar";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{
    email?: string;
    password?: string;
    form?: string;
  }>({});
  const [submitting, setSubmitting] = useState(false);
  async function startDemo() {
    setSubmitting(true);
    setErrors({});
    try {
      await onDemo();
    } catch (error) {
      setErrors({
        form: error instanceof Error ? error.message : "Demo sign-in failed.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next: typeof errors = {};
    if (!/^\S+@\S+\.\S+$/.test(email))
      next.email = ar
        ? "أدخل بريدًا إلكترونيًا صالحًا للعمل."
        : "Enter a valid email address.";
    if (!password)
      next.password = ar ? "كلمة المرور مطلوبة." : "Password is required.";
    setErrors(next);
    if (Object.keys(next).length) return;
    setSubmitting(true);
    try {
      await onLogin({ email, password });
    } catch (error) {
      setErrors((current) => ({
        ...current,
        form:
          error instanceof Error
            ? error.message
            : ar
              ? "تعذر تسجيل الدخول."
              : "Sign-in failed.",
      }));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="login-form" onSubmit={submit} noValidate>
      <div className="field">
        <label htmlFor="work-email">{ar ? "بريد العمل" : "Work email"}</label>
        <input
          id="work-email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          aria-invalid={Boolean(errors.email)}
          aria-describedby={errors.email ? "work-email-error" : undefined}
          placeholder="name@company.com"
        />
        {errors.email ? (
          <p id="work-email-error" className="field-error" role="alert">
            {errors.email}
          </p>
        ) : null}
      </div>
      <div className="field">
        <div className="label-row">
          <label htmlFor="password">{ar ? "كلمة المرور" : "Password"}</label>
          <span>{ar ? "اتصال آمن" : "Secure session"}</span>
        </div>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          aria-invalid={Boolean(errors.password)}
          aria-describedby={errors.password ? "password-error" : undefined}
        />
        {errors.password ? (
          <p id="password-error" className="field-error" role="alert">
            {errors.password}
          </p>
        ) : null}
      </div>
      {errors.form ? (
        <p className="form-error" role="alert">
          {errors.form}
        </p>
      ) : null}
      <button
        className="button button--primary button--wide"
        type="submit"
        disabled={submitting}
      >
        <LockKeyhole size={17} aria-hidden="true" />{" "}
        {submitting
          ? ar
            ? "جارٍ التحقق…"
            : "Verifying…"
          : ar
            ? "تسجيل الدخول"
            : "Sign in"}{" "}
        <ArrowRight size={16} aria-hidden="true" />
      </button>
      <div className="form-separator">
        <span>{ar ? "أو استكشف بأمان" : "or explore safely"}</span>
      </div>
      <button
        className="button button--demo button--wide"
        type="button"
        onClick={startDemo}
      >
        <FlaskConical size={17} aria-hidden="true" />{" "}
        {ar ? "فتح مساحة تجريبية خيالية" : "Open fictional demo workspace"}
      </button>
      <p className="form-note">
        {ar
          ? "البيانات التجريبية منفصلة كليًا عن أي بيانات متصلة."
          : "Demo records are fully separated from connected company data."}
      </p>
    </form>
  );
}
