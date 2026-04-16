import { proxy } from "./src/proxy";

export default proxy;
export { proxy };

export const config = {
  matcher: ["/", "/((?!api|_next|_vercel|.*\\..*).*)"],
};
