import type { ReactNode } from "react";
import {
  IconBrandYoutube,
  IconBrandTelegram,
  IconBrandInstagram,
  IconBrandLinkedin,
  IconLink
} from "@tabler/icons-react";

// Inline monochrome messenger marks keep all assets local and consistently sized.
const messengerPaths: Record<string, ReactNode> = {
  eitaa: (
    <>
      <path d="M19 12a7 7 0 1 0-12 5l-2 4 5-2a7 7 0 0 0 9-7Z" />
      <path d="M8 12h8m-8 0a4 4 0 0 1 8 0m-8 0a4 4 0 0 0 6 3" />
    </>
  ),
  rubika: (
    <>
      <path d="m12 2 9 5v10l-9 5-9-5V7Z" />
      <path d="m3 7 9 5 9-5M12 12v10M7.5 4.5l9 5v10m-13.5-7 9 5 9-5" />
    </>
  ),
  bale: (
    <>
      <path d="M20 11a8 8 0 1 0-14 5l-2 5 6-2a8 8 0 0 0 10-8Z" />
      <path d="m8 11 3 3 6-7" />
    </>
  ),
  soroush: (
    <>
      <path d="M20 10a8 8 0 0 0-16 0c0 4 3 7 7 7l5 4v-5c3-1 4-3 4-6Z" />
      <path d="M8 8h8m-8 4h6" />
    </>
  )
};

export function SocialIcon({ name }: { name: string }) {
  const Icon = (
    {
      youtube: IconBrandYoutube,
      telegram: IconBrandTelegram,
      instagram: IconBrandInstagram,
      linkedin: IconBrandLinkedin
    } as Record<string, typeof IconLink>
  )[name];
  if (Icon) return <Icon className="w-5 h-5" aria-hidden stroke={1.6} />;
  if (messengerPaths[name])
    return (
      <svg
        className="w-5 h-5"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        {messengerPaths[name]}
      </svg>
    );
  return <IconLink className="w-5 h-5" aria-hidden stroke={1.6} />;
}
