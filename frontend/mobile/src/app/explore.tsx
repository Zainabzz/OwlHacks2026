import { Text, View } from 'react-native';

export default function ExploreScreen() {
  return (
    <View className="flex-1 items-center justify-center bg-slate-950 px-6">
      <Text className="text-2xl font-bold text-cyan-400">Explore</Text>
      <Text className="mt-2 text-center text-slate-300">
        Route debugging screen for the OwlHacks app.
      </Text>
    </View>
  );
}
