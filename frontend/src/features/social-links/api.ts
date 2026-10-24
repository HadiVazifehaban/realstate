import { apiBaseUrl } from "@/lib/api-base-url";

export const socialAdminRoles = ["ROLE_ADMIN", "ROLE_SUPER_ADMIN", "admin", "super_admin"];
export const socialPlatforms = {
  youtube: "یوتیوب",
  telegram: "تلگرام",
  instagram: "اینستاگرام",
  linkedin: "لینکدین",
  eitaa: "ایتا",
  rubika: "روبیکا",
  bale: "بله",
  soroush: "سروش",
  link: "پیوند دیگر"
} as const;
export type SocialIconName = keyof typeof socialPlatforms;
export type SocialLinkValues = {
  platform_key: string;
  display_name: string;
  icon_name: SocialIconName;
  url: string;
  is_active: boolean;
  sort_order: number;
};
export type SocialLink = SocialLinkValues & { id: string };
export const socialKeys = { public: ["footer-social-links"], admin: ["admin-social-links"] };

export function safeSocialUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return (
      ["https:", "http:"].includes(url.protocol) &&
      !url.username &&
      !url.password &&
      !/[\s\\]/.test(value)
    );
  } catch {
    return false;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...init?.headers }
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : `خطا در ذخیره یا دریافت پیوندها (${response.status})`
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export const fetchPublicSocialLinks = () => request<SocialLink[]>("/site/social-links");
export const fetchAdminSocialLinks = () => request<SocialLink[]>("/admin/social-links");
export const saveSocialLink = (values: SocialLinkValues, id?: string) =>
  request<SocialLink>(`/admin/social-links${id ? `/${encodeURIComponent(id)}` : ""}`, {
    method: id ? "PUT" : "POST",
    body: JSON.stringify(values)
  });
export const toggleSocialLink = (id: string, is_active: boolean) =>
  request<SocialLink>(`/admin/social-links/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify({ is_active })
  });
export const deleteSocialLink = (id: string) =>
  request<void>(`/admin/social-links/${encodeURIComponent(id)}`, { method: "DELETE" });
export const reorderSocialLinks = (ids: string[]) =>
  request<SocialLink[]>("/admin/social-links/reorder", {
    method: "PUT",
    body: JSON.stringify({ ids })
  });
