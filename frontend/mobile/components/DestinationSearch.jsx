import { useEffect, useRef, useState } from "react";
import { View, Text, TextInput, TouchableOpacity, ScrollView, ActivityIndicator, StyleSheet } from "react-native";
import { createSearchSession, suggestPlaces, retrievePlace } from "../src/services/search";

export default function DestinationSearch({ location, theme, onSelect, onSubmit, value = null, label = "Destination", placeholder = "Where are you going?" }) {
  const [query, setQuery] = useState(value?.name || "");
  const [selected, setSelected] = useState(Boolean(value));
  const [suggestions, setSuggestions] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [session, setSession] = useState(createSearchSession);
  const generation = useRef(0);

  const [previousValue, setPreviousValue] = useState(value);
  // Preserve a draft when editing clears the parent's resolved coordinates.
  // External selections (GPS/swap) replace the draft before rendering children.
  if (value !== previousValue) {
    setPreviousValue(value);
    if (value) {
      setQuery(value.name || `${value.latitude}, ${value.longitude}`);
      setSelected(true);
      setSuggestions([]);
      setBusy(false);
      setError("");
    }
  }

  useEffect(() => {
    if (value) generation.current += 1;
  }, [value]);

  useEffect(() => {
    if (selected || query.trim().length < 2) return;
    let cancelled = false;
    const version = generation.current;
    const timer = setTimeout(async () => {
      setBusy(true);
      try {
        const results = await suggestPlaces(query.trim(), session, location);
        if (!cancelled && generation.current === version) {
          setSuggestions(results);
          setError(results.length ? "" : "No places found. Try a more specific address.");
        }
      } catch (err) {
        if (!cancelled && generation.current === version) setError(err.message);
      } finally {
        if (!cancelled && generation.current === version) setBusy(false);
      }
    }, 350);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [query, selected, session, location]);

  useEffect(() => () => { generation.current += 1; }, []);

  const changeQuery = text => {
    generation.current += 1;
    setQuery(text);
    setSelected(false);
    setSuggestions([]);
    setError("");
    setBusy(false);
    onSelect(null);
  };

  const selectPlace = async suggestion => {
    const version = ++generation.current;
    setBusy(true);
    setSelected(true);
    setSuggestions([]);
    setError("");
    try {
      const place = await retrievePlace(suggestion.id, session);
      if (version !== generation.current) return;
      setQuery(place.name);
      setSelected(true);
      setSuggestions([]);
      onSelect(place);
    } catch (err) {
      if (version === generation.current) setError(`${err.message} Edit the search to try again.`);
    } finally {
      if (version === generation.current) {
        setBusy(false);
        setSession(createSearchSession());
      }
    }
  };

  return (
    <View style={{ flexShrink: 1 }}>
      <Text style={{ color: theme.textSecondary, fontSize: 12 }}>{label}</Text>
      <TextInput
        value={query}
        onChangeText={changeQuery}
        placeholder={placeholder}
        placeholderTextColor={theme.textSecondary}
        style={[styles.input, { color: theme.text }]}
        accessibilityLabel={`Search ${label.toLowerCase()}`}
        autoCorrect={false}
        selectTextOnFocus
        returnKeyType="search"
        onSubmitEditing={() => {
          if (value) onSubmit?.();
          else if (!busy && suggestions.length === 1) selectPlace(suggestions[0]);
          else setError("Choose a place from the results below.");
        }}
      />
      {busy && <ActivityIndicator color={theme.primary} accessibilityLabel="Searching places" />}
      {!!error && <Text accessibilityRole="alert" style={{ color: theme.textSecondary, marginBottom: 10 }}>{error}</Text>}
      {suggestions.length > 0 && (
        <ScrollView style={styles.results} keyboardShouldPersistTaps="handled" nestedScrollEnabled>
          {suggestions.map(item => (
            <TouchableOpacity key={item.id} disabled={busy} onPress={() => selectPlace(item)} accessibilityRole="button"
              style={[styles.result, { borderColor: theme.border }]}>
              <Text style={{ color: theme.text, fontWeight: "600" }}>{item.name}</Text>
              <Text style={{ color: theme.textSecondary }}>{item.description}</Text>
            </TouchableOpacity>
          ))}
          <Text style={{ color: theme.textSecondary, fontSize: 11 }}>Search by Mapbox</Text>
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  input: { minHeight: 55, fontSize: 19, paddingVertical: 10, marginBottom: 12 },
  results: { maxHeight: 180, marginBottom: 12 },
  result: { paddingVertical: 12, borderBottomWidth: 1 },
});
