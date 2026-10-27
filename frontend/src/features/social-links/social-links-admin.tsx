"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuthContext } from "@/hooks/use-auth";
import { SocialIcon } from "./social-icon";
import {
  deleteSocialLink,
  fetchAdminSocialLinks,
  reorderSocialLinks,
  safeSocialUrl,
  saveSocialLink,
  socialAdminRoles,
  socialKeys,
  socialPlatforms,
  toggleSocialLink,
  type SocialLink,
  type SocialLinkValues,
  type SocialIconName
} from "./api";

const empty: SocialLinkValues = {
  platform_key: "telegram",
  display_name: "تلگرام",
  icon_name: "telegram",
  url: "",
  is_active: true,
  sort_order: 0
};
const control =
  "rounded-xl border border-[#ffd8be]/20 bg-[#060b13]/80 px-3 py-2 text-white disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-[#ffd8be]";
type Action =
  | { kind: "save"; values: SocialLinkValues; id?: string }
  | { kind: "toggle"; link: SocialLink }
  | { kind: "delete"; id: string }
  | { kind: "reorder"; links: SocialLink[] };

export function SocialLinksAdmin() {
  const auth = useAuthContext();
  const allowed = auth.roles.some((role) => socialAdminRoles.includes(role));
  const client = useQueryClient();
  const [values, setValues] = useState<SocialLinkValues>(empty);
  const [editing, setEditing] = useState<string>();
  const [feedback, setFeedback] = useState("");
  const locked = useRef(false);
  const query = useQuery({
    queryKey: socialKeys.admin,
    queryFn: fetchAdminSocialLinks,
    enabled: !auth.isLoading && allowed,
    retry: false
  });
  const mutation = useMutation({
    mutationFn: (action: Action) => {
      if (action.kind === "save")
        return saveSocialLink(action.values, action.id).then(() => undefined);
      if (action.kind === "toggle")
        return toggleSocialLink(action.link.id, !action.link.is_active).then(() => undefined);
      if (action.kind === "delete") return deleteSocialLink(action.id);
      return reorderSocialLinks(action.links.map((link) => link.id)).then(() => undefined);
    },
    onMutate: async (action) => {
      setFeedback("");
      await client.cancelQueries({ queryKey: socialKeys.admin });
      const previous = client.getQueryData<SocialLink[]>(socialKeys.admin);
      if (action.kind === "toggle")
        client.setQueryData(
          socialKeys.admin,
          previous?.map((link) =>
            link.id === action.link.id ? { ...link, is_active: !link.is_active } : link
          )
        );
      if (action.kind === "reorder") client.setQueryData(socialKeys.admin, action.links);
      return { previous };
    },
    onError: (error, _, context) => {
      if (context?.previous) client.setQueryData(socialKeys.admin, context.previous);
      setFeedback(error.message);
      toast.error(error.message);
    },
    onSuccess: (_, action) => {
      toast.success("تغییرات پیوندها ذخیره شد.");
      setFeedback("تغییرات ذخیره شد.");
      if (typeof BroadcastChannel !== "undefined") {
        const channel = new BroadcastChannel("shekarchi-social-links");
        channel.postMessage({ type: "changed" });
        channel.close();
      }
      window.dispatchEvent(new Event("shekarchi:social-links-changed"));
      if (action.kind === "save" || (action.kind === "delete" && action.id === editing)) {
        setEditing(undefined);
        setValues(empty);
      }
    },
    onSettled: async () => {
      try {
        await Promise.all([
          client.invalidateQueries({ queryKey: socialKeys.admin }),
          client.invalidateQueries({ queryKey: socialKeys.public })
        ]);
      } finally {
        locked.current = false;
      }
    }
  });
  const act = (action: Action) => {
    if (locked.current) return;
    locked.current = true;
    mutation.mutate(action);
  };
  const links = query.data ?? [];
  const move = (index: number, offset: number) => {
    const reordered = [...links];
    [reordered[index], reordered[index + offset]] = [reordered[index + offset], reordered[index]];
    act({ kind: "reorder", links: reordered });
  };
  if (auth.isLoading) return <p role="status">در حال بررسی دسترسی…</p>;
  if (!allowed) return <p role="alert">دسترسی به این بخش فقط برای مدیر سامانه مجاز است.</p>;

  return (
    <section dir="rtl" className="mx-auto w-full max-w-5xl space-y-6 p-4 text-white md:p-8">
      <header>
        <h1 className="text-2xl font-bold">پیوندهای شبکه‌های اجتماعی</h1>
        <p className="mt-2 text-sm text-gray-400">
          پیوندهای فعال در فوتر عمومی نمایش داده می‌شوند. ترتیب را با دکمه‌های بالا و پایین تغییر دهید.
        </p>
      </header>
      {query.isPending && <p role="status">در حال دریافت پیوندها…</p>}
      {query.isError && (
        <div role="alert">
          {query.error.message}{" "}
          <button className={control} onClick={() => void query.refetch()}>
            تلاش دوباره
          </button>
        </div>
      )}
      {feedback && (
        <p role="status" className="text-[#ffd8be]">
          {feedback}
        </p>
      )}
      <form
        aria-label={editing ? "ویرایش پیوند" : "افزودن پیوند"}
        className="grid gap-4 rounded-2xl border border-[#ffd8be]/15 bg-[#060b13]/80 p-5 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (!safeSocialUrl(values.url)) {
            setFeedback("نشانی معتبر http یا https وارد کنید.");
            return;
          }
          const sort_order = editing
            ? values.sort_order
            : Math.max(-1, ...links.map((link) => link.sort_order)) + 1;
          act({ kind: "save", values: { ...values, sort_order }, id: editing });
        }}
      >
        <fieldset disabled={mutation.isPending || !query.isSuccess} className="contents">
          <label className="grid gap-2">
            پلتفرم
            <select
              className={control}
              value={values.platform_key in socialPlatforms ? values.platform_key : "custom"}
              onChange={(event) => {
                const key = event.target.value;
                setValues({
                  ...values,
                  platform_key: key,
                  icon_name: key === "custom" ? "link" : (key as SocialIconName),
                  display_name: key === "custom" ? "" : socialPlatforms[key as SocialIconName]
                });
              }}
            >
              {Object.entries(socialPlatforms)
                .filter(([key]) => key !== "link")
                .map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              <option value="custom">سایر</option>
            </select>
          </label>
          <label className="grid gap-2">
            کلید پلتفرم
            <input
              className={control}
              dir="ltr"
              required
              pattern="[a-z][a-z0-9_-]*"
              maxLength={64}
              value={values.platform_key}
              onChange={(event) => setValues({ ...values, platform_key: event.target.value })}
            />
          </label>
          <label className="grid gap-2">
            نام نمایشی
            <input
              className={control}
              required
              maxLength={100}
              value={values.display_name}
              onChange={(event) => setValues({ ...values, display_name: event.target.value })}
            />
          </label>
          <label className="grid gap-2">
            آیکون
            <select
              className={control}
              value={values.icon_name}
              onChange={(event) =>
                setValues({ ...values, icon_name: event.target.value as SocialIconName })
              }
            >
              {Object.entries(socialPlatforms).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-2 sm:col-span-2">
            نشانی مقصد
            <input
              className={control}
              type="url"
              dir="ltr"
              required
              maxLength={2048}
              placeholder="https://…"
              value={values.url}
              onChange={(event) => setValues({ ...values, url: event.target.value })}
            />
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={values.is_active}
              onChange={(event) => setValues({ ...values, is_active: event.target.checked })}
            />
            نمایش در فوتر
          </label>
          <div className="flex gap-2">
            <button className={control} type="submit">
              {mutation.isPending ? "در حال ذخیره…" : editing ? "ذخیره تغییرات" : "افزودن پیوند"}
            </button>
            {editing && (
              <button
                type="button"
                className={control}
                onClick={() => {
                  setEditing(undefined);
                  setValues(empty);
                }}
              >
                انصراف
              </button>
            )}
          </div>
        </fieldset>
      </form>
      {query.isSuccess && !links.length && <p>هنوز پیوندی ثبت نشده است.</p>}
      <ul className="space-y-3" aria-label="پیوندهای ثبت‌شده">
        {links.map((link, index) => (
          <li
            key={link.id}
            className="flex flex-wrap items-center gap-3 rounded-2xl border border-[#ffd8be]/15 bg-[#060b13]/80 p-4"
          >
            <SocialIcon name={link.icon_name} />
            <div className="min-w-0 flex-1">
              <strong>{link.display_name}</strong>
              <p className="break-all text-xs text-gray-400" dir="ltr">
                {link.url}
              </p>
            </div>
            <button
              className={control}
              disabled={mutation.isPending}
              role="switch"
              aria-checked={link.is_active}
              aria-label={`نمایش ${link.display_name}`}
              onClick={() => act({ kind: "toggle", link })}
            >
              {link.is_active ? "فعال" : "پنهان"}
            </button>
            <button
              className={control}
              disabled={mutation.isPending}
              onClick={() => {
                setEditing(link.id);
                setValues({
                  platform_key: link.platform_key,
                  display_name: link.display_name,
                  icon_name: link.icon_name,
                  url: link.url,
                  is_active: link.is_active,
                  sort_order: link.sort_order
                });
              }}
            >
              ویرایش {link.display_name}
            </button>
            <button
              className={control}
              disabled={mutation.isPending}
              onClick={() => {
                if (window.confirm(`پیوند «${link.display_name}» حذف شود؟`))
                  act({ kind: "delete", id: link.id });
              }}
            >
              حذف {link.display_name}
            </button>
            <button
              className={control}
              aria-label={`انتقال ${link.display_name} به بالا`}
              disabled={mutation.isPending || index === 0}
              onClick={() => move(index, -1)}
            >
              ↑
            </button>
            <button
              className={control}
              aria-label={`انتقال ${link.display_name} به پایین`}
              disabled={mutation.isPending || index === links.length - 1}
              onClick={() => move(index, 1)}
            >
              ↓
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
