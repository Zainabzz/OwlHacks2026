import { View, Text, Pressable } from "react-native";

export default function HomeScreen() {
  return (
    <View className="flex-1 items-center justify-center bg-slate-950 px-6">
      <Text className="text-3xl font-bold text-blue-400">
        OwlHacks 2026
      </Text>

      <Text className="mt-3 text-center text-slate-300">
        Weather-aware routing app
      </Text>

      <Pressable className="mt-6 rounded-lg bg-blue-600 px-6 py-3">
        <Text className="font-semibold text-white">
          Find a Route
        </Text>
      </Pressable>
    </View>
  );
}