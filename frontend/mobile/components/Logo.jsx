import { Image } from "react-native";

const logo = require("../assets/logo.png");

export default function Logo({ size = 48 }) {
  return (
    <Image
      source={logo}
      style={{ width: size, height: size, resizeMode: "contain" }}
      accessibilityLabel="OwlRoute logo"
    />
  );
}
