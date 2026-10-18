export type ThemePreset = "soft-pink" | "rosy-purple" | "lavender" | "custom";

export interface ThemeTokens {
  background: string;
  surface: string;
  surfaceStrong: string;
  surfaceHover: string;
  surfaceSelected: string;
  border: string;
  borderStrong: string;
  text: string;
  muted: string;
  primary: string;
  accent: string;
  nav: string;
  focus: string;
  gradientStart: string;
  gradientEnd: string;
  sideStart: string;
  sideEnd: string;
}

export const themePresets: Record<Exclude<ThemePreset, "custom">, ThemeTokens> = {
  "soft-pink": {
    background: "#fbf7fc",
    surface: "#ffffff",
    surfaceStrong: "#fff7fb",
    surfaceHover: "#ffe7f3",
    surfaceSelected: "#ffd6ec",
    border: "#eadbea",
    borderStrong: "#d6afd2",
    text: "#44233d",
    muted: "#7a6374",
    primary: "#ff8acb",
    accent: "#b992ff",
    nav: "#3e2038",
    focus: "#ff7bc3",
    gradientStart: "#ffd6ec",
    gradientEnd: "#e8c7ff",
    sideStart: "#3e2038",
    sideEnd: "#7f2b69"
  },
  "rosy-purple": {
    background: "hsl(270 20% 96%)",
    surface: "#ffffff",
    surfaceStrong: "hsl(270 90% 98%)",
    surfaceHover: "hsl(270 90% 94%)",
    surfaceSelected: "hsl(270 90% 90%)",
    border: "hsl(270 28% 86%)",
    borderStrong: "hsl(270 38% 72%)",
    text: "hsl(270 26% 20%)",
    muted: "hsl(270 12% 45%)",
    primary: "hsl(260 90% 75%)",
    accent: "hsl(270 90% 50%)",
    nav: "hsl(270 34% 18%)",
    focus: "hsl(291 70% 62%)",
    gradientStart: "hsl(250 90% 75%)",
    gradientEnd: "hsl(291 70% 79%)",
    sideStart: "hsl(270 90% 90%)",
    sideEnd: "hsl(270 20% 96%)"
  },
  lavender: {
    background: "#f7f5ff",
    surface: "#ffffff",
    surfaceStrong: "#fbfaff",
    surfaceHover: "#efe9ff",
    surfaceSelected: "#e6ddff",
    border: "#ddd5f4",
    borderStrong: "#bca7ea",
    text: "#332c45",
    muted: "#70677f",
    primary: "#a98cff",
    accent: "#f08bc5",
    nav: "#302645",
    focus: "#9c74ff",
    gradientStart: "#e9dcff",
    gradientEnd: "#ffd8ec",
    sideStart: "#302645",
    sideEnd: "#6a4a8f"
  }
};

export const themePresetsDark: Record<Exclude<ThemePreset, "custom">, ThemeTokens> = {
  "soft-pink": {
    background: "#181318",
    surface: "#221a23",
    surfaceStrong: "#2a1f2c",
    surfaceHover: "#341f33",
    surfaceSelected: "#48253f",
    border: "#372c38",
    borderStrong: "#5b4459",
    text: "#f5e7f1",
    muted: "#b89fb3",
    primary: "#ff8fce",
    accent: "#c4a3ff",
    nav: "#100b11",
    focus: "#ff7bc3",
    gradientStart: "#ff8fce",
    gradientEnd: "#c4a3ff",
    sideStart: "#2a1226",
    sideEnd: "#3f1535"
  },
  "rosy-purple": {
    background: "hsl(270 18% 10%)",
    surface: "hsl(270 16% 14%)",
    surfaceStrong: "hsl(270 20% 17%)",
    surfaceHover: "hsl(270 30% 22%)",
    surfaceSelected: "hsl(270 35% 28%)",
    border: "hsl(270 18% 26%)",
    borderStrong: "hsl(270 24% 40%)",
    text: "hsl(270 30% 92%)",
    muted: "hsl(270 12% 64%)",
    primary: "hsl(260 90% 78%)",
    accent: "hsl(285 90% 72%)",
    nav: "hsl(270 30% 8%)",
    focus: "hsl(291 80% 70%)",
    gradientStart: "hsl(260 80% 70%)",
    gradientEnd: "hsl(291 75% 70%)",
    sideStart: "hsl(270 40% 16%)",
    sideEnd: "hsl(285 50% 24%)"
  },
  lavender: {
    background: "#15121d",
    surface: "#1e1a28",
    surfaceStrong: "#24202f",
    surfaceHover: "#2c2640",
    surfaceSelected: "#373050",
    border: "#332d44",
    borderStrong: "#4f4668",
    text: "#ece8fb",
    muted: "#a59ec0",
    primary: "#b79bff",
    accent: "#f08bc5",
    nav: "#100d18",
    focus: "#a98cff",
    gradientStart: "#b79bff",
    gradientEnd: "#f08bc5",
    sideStart: "#211b34",
    sideEnd: "#3a2c5c"
  }
};

export const defaultCustomTheme: ThemeTokens = { ...themePresets["soft-pink"] };

// Dark neutral base shared by the custom palette in dark mode. The user's brand
// colors (primary/accent/focus + gradient) are kept so a custom pink still reads
// as pink, just on dark surfaces.
const customDarkBase = {
  background: "#181318",
  surface: "#221a23",
  surfaceStrong: "#2a1f2c",
  surfaceHover: "#341f33",
  surfaceSelected: "#48253f",
  border: "#372c38",
  borderStrong: "#5b4459",
  text: "#f5e7f1",
  muted: "#b89fb3",
  nav: "#100b11",
  sideStart: "#241226",
  sideEnd: "#3a1533"
} as const;

export function deriveDarkTokens(light: ThemeTokens): ThemeTokens {
  return {
    ...customDarkBase,
    primary: light.primary,
    accent: light.accent,
    focus: light.focus,
    gradientStart: light.primary,
    gradientEnd: light.accent
  };
}

export function getThemeTokens(
  preset: ThemePreset,
  customTheme: ThemeTokens = defaultCustomTheme,
  darkMode = false
): ThemeTokens {
  if (preset === "custom") {
    return darkMode ? deriveDarkTokens(customTheme) : customTheme;
  }
  return (darkMode ? themePresetsDark[preset] : themePresets[preset]) ?? (darkMode ? themePresetsDark["soft-pink"] : themePresets["soft-pink"]);
}

export function themeCssVariables(tokens: ThemeTokens): Record<string, string> {
  const readable = readableForeground([tokens.surface],tokens.text);
  const safeSurface = (color:string) => contrastRatio(readable,color)>=4.5 ? color : tokens.surface;
  const canvas=safeSurface(tokens.background), strong=safeSurface(tokens.surfaceStrong), hover=safeSurface(tokens.surfaceHover);
  const selected=safeSurface(tokens.surfaceSelected);
  const muted = readableForeground([tokens.surface,strong,hover,selected,canvas],tokens.muted);
  // Keep the app's existing pastel action gradient. An extreme custom palette
  // falls back to a readable themed fill instead of unreadable button text.
  let actionStart = tokens.gradientStart, actionEnd = tokens.gradientEnd;
  const a = colorChannels(actionStart), b = colorChannels(actionEnd);
  const actionSamples = Array.from({length: 21}, (_, i) =>
    `rgb(${a.map((value, k) => Math.round((value + (b[k] - value) * i / 20) * 255)).join(",")})`);
  let actionText = readableForeground(actionSamples, tokens.text);
  if (actionSamples.some((color) => contrastRatio(actionText, color) < 4.5)) {
    actionStart = actionEnd = selected;
    actionText = readableForeground([selected], tokens.text);
  }
  const sideText=readableForeground([tokens.sideStart,tokens.sideEnd],"#ffffff");
  const sideFallback=sideText==="#ffffff"?"#111111":"#ffffff";
  const sideStart=contrastRatio(sideText,tokens.sideStart)>=4.5?tokens.sideStart:sideFallback;
  const sideEnd=contrastRatio(sideText,tokens.sideEnd)>=4.5?tokens.sideEnd:sideFallback;
  return {
    "--action-bg":actionStart,
    "--action-start":actionStart,
    "--action-end":actionEnd,
    "--action-fg":actionText,
    "--danger-fg":readableForeground([strong,hover], "#b42334"),
    "--on-selected":readableForeground([selected],tokens.text),
    "--on-sidebar":sideText,
    "--bg": canvas,
    "--surface": tokens.surface,
    "--surface-strong": strong,
    "--surface-hover": hover,
    "--surface-selected": selected,
    "--surface-success": strong,
    "--border": tokens.border,
    "--border-strong": tokens.borderStrong,
    "--text": readable,
    "--muted": muted,
    "--primary": tokens.primary,
    "--accent": tokens.accent,
    "--blue": tokens.primary,
    "--green": tokens.accent,
    "--navy": tokens.nav,
    "--focus": readableForeground([tokens.surface],tokens.focus),
    "--gradient-start": tokens.gradientStart,
    "--gradient-end": tokens.gradientEnd,
    "--side-start": sideStart,
    "--side-end": sideEnd,
    "--primary-gradient": `linear-gradient(135deg, ${tokens.gradientStart} 0%, ${tokens.gradientEnd} 100%)`,
    "--side-gradient": `linear-gradient(160deg, ${sideStart} 0%, ${sideEnd} 100%)`
  };
}

export function colorChannels(value: string): number[] {
  const color = value.trim();
  if (/^#[0-9a-f]{3}$/i.test(color)) return color.slice(1).split("").map((c)=>parseInt(c+c,16)/255);
  if (/^#[0-9a-f]{6}$/i.test(color)) return [1,3,5].map((i)=>parseInt(color.slice(i,i+2),16)/255);
  const parts = color.match(/-?[\d.]+/g)?.map(Number) ?? [];
  if (color.startsWith("rgb") && parts.length>=3) return parts.slice(0,3).map((n)=>n/255);
  if (color.startsWith("hsl") && parts.length>=3) {
    const h=((parts[0]%360)+360)%360/360, s=parts[1]/100,l=parts[2]/100;
    const a=s*Math.min(l,1-l);
    return [0,8,4].map((n)=>{const k=(n+h*12)%12;return l-a*Math.max(-1,Math.min(k-3,9-k,1));});
  }
  return [0,0,0];
}
export function contrastRatio(first: string,second: string):number {
  const luminance=(color:string)=>colorChannels(color).map((n)=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4)
    .reduce((sum,n,i)=>sum+n*[.2126,.7152,.0722][i],0);
  const a=luminance(first),b=luminance(second);
  return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
}
export function readableForeground(backgrounds: string[],preferred: string):string {
  const score=(color:string)=>Math.min(...backgrounds.map((bg)=>contrastRatio(color,bg)));
  if(score(preferred)>=4.5)return preferred;
  return score("#000000")>=score("#ffffff")?"#000000":"#ffffff";
}
