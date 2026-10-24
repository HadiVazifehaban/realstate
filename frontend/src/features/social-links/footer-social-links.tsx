"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchPublicSocialLinks, safeSocialUrl, socialKeys } from "./api";
import { SocialIcon } from "./social-icon";

export function FooterSocialLinks() {
  const query = useQuery({
    queryKey: socialKeys.public,
    queryFn: fetchPublicSocialLinks,
    staleTime: 0,
    refetchInterval: 60_000,
    retry: 1
  });
  const links = (query.data ?? [])
    .filter((link) => link.is_active && safeSocialUrl(link.url))
    .sort((a, b) => a.sort_order - b.sort_order || a.id.localeCompare(b.id));
  // An unavailable configuration never substitutes invented accounts/URLs.
  if (!links.length) return null;
  return (
    <nav
      aria-label="شبکه‌های اجتماعی شکارچی"
      className="footer-social-links flex flex-wrap gap-2 mt-5"
    >
      {links.map((link) => (
        <a
          key={link.id}
          href={link.url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={link.display_name}
          title={link.display_name}
          className="inline-flex size-11 items-center justify-center rounded-xl border border-[#ffd8be]/15 bg-[#060b13]/80 text-[#c6b5aa] hover:text-[#ffd8be] hover:shadow-[0_0_16px_#ffd8be26] transition-colors focus-visible:outline-2 focus-visible:outline-[#ffd8be]"
        >
          <SocialIcon name={link.icon_name} />
        </a>
      ))}
    </nav>
  );
}
