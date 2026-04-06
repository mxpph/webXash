<template>
  <div class="window no-resize" name="WebTransport">
    <div class="webtransport-wrapper">
      <label for="webtransport-input-1"></label>
      <input id="webtransport-input-1" v-model="wtServerUrl" type="text" placeholder="URL" />
      <label for="webtransport-input-2"></label>
      <input id="webtransport-input-2" v-model="wtServerCertificateHashBase64" type="text" placeholder="Certificate hash" />
    </div>
  </div>
</template>

<script setup lang="ts">
  import { storeToRefs } from 'pinia';
  import { useXashStore } from '/@/stores/store.ts';

  // Data

  const store = useXashStore();
  const { wtServerUrl, wtServerCertificateHashBase64 } = storeToRefs(store);

</script>

<style scoped lang="scss">
  .webtransport-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;

    #webtransport-input {
      width: 100%;
    }
  }
</style>
