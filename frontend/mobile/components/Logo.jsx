import Svg, { Path, Text as SvgText } from "react-native-svg";

export default function Logo({ color = "#277A59", size = 48 }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 64 64">
      <Path
        d="M32 4C18 4 8 14 8 28c0 18 24 32 24 32s24-14 24-32C56 14 46 4 32 4Z"
        fill="none"
        stroke={color}
        strokeWidth={4}
        strokeLinejoin="round"
      />

      <SvgText
        x="32"
        y="39"
        fontSize="30"
        fontWeight="bold"
        fill={color}
        textAnchor="middle"
      >
        P
      </SvgText>
    </Svg>
  );
}