import Image from "next/image";

type CategoryIconProps = {
  slug: string;
  name: string;
  size?: number;
};

type CategoryToken =
  | "suspension"
  | "brake"
  | "cooling"
  | "engine"
  | "transmission"
  | "electrics"
  | "body"
  | "fluids"
  | "wheels"
  | "parts";

const CATEGORY_ICON_SRC: Record<CategoryToken, string> = {
  suspension: "/icons/categories/street-wheel.svg",
  brake: "/icons/categories/brakes.svg",
  cooling: "/icons/categories/cooling.svg",
  engine: "/icons/categories/energy.svg",
  transmission: "/icons/categories/clutch.svg",
  electrics: "/icons/categories/electricity.svg",
  body: "/icons/categories/body.svg",
  fluids: "/icons/categories/chemicals.svg",
  wheels: "/icons/categories/wheel.svg",
  parts: "/icons/categories/engine.svg",
};

function resolveCategoryToken(slug: string, name: string): CategoryToken {
  const token = `${slug} ${name}`.toLowerCase();

  if (/(подвес|підвіс|рулев|кермов|susp|steer)/.test(token)) {
    return "suspension";
  }
  if (/(тормоз|гальм|brake|abs)/.test(token)) {
    return "brake";
  }
  if (/(охлаж|опал|охолод|кондиц|cool|heating|radiator|термостат)/.test(token)) {
    return "cooling";
  }
  if (/(двиг|двигун|выхлоп|вихлоп|engine|exhaust|nox|турб)/.test(token)) {
    return "engine";
  }
  if (/(сцеп|зчеп|трансм|кпп|gear|transm|clutch|шрус)/.test(token)) {
    return "transmission";
  }
  if (/(электр|електр|освещ|освіт|lighting|ignition|аккум|акум|стартер|генератор)/.test(token)) {
    return "electrics";
  }
  if (/(кузов|кузова|body|бампер|двер|зеркал|дзеркал|фар|lamp|headlight|оптик)/.test(token)) {
    return "body";
  }
  if (/(хим|хім|аксесс|аксесу|fluid|масл|олив|oil|антифриз|герметик)/.test(token)) {
    return "fluids";
  }
  if (/(шин|шини|диск|колес|коліс|wheel|tire|tyre|rim)/.test(token)) {
    return "wheels";
  }

  return "parts";
}

function RasterIcon({ src, size = 18 }: { src: string; size?: number }) {
  return (
    <Image src={src} width={size} height={size} alt="" aria-hidden />
  );
}

export function CategoryParentIcon({ slug, name, size = 18 }: CategoryIconProps) {
  const token = resolveCategoryToken(slug, name);
  return <RasterIcon src={CATEGORY_ICON_SRC[token]} size={size} />;
}
