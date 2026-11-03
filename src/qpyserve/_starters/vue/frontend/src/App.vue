<script setup>
import { ref } from 'vue';

const result = ref('Ready');

async function callPython() {
  result.value = 'Loading...';
  try {
    const response = await fetch('/api/hello');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const { message, time } = await response.json();
    result.value = `${message}\n${time}`;
  } catch (error) {
    result.value = `API error: ${error.message}`;
  }
}
</script>

<template>
  <main>
    <h1>QPyServe is running.</h1>
    <p>One Python command, a full Vue frontend, and a real API.</p>
    <button type="button" @click="callPython">Call Python API</button>
    <output role="status" aria-live="polite">{{ result }}</output>
    <p><a href="/docs">API documentation</a></p>
  </main>
</template>
