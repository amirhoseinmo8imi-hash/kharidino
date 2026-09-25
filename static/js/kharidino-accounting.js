document.addEventListener('DOMContentLoaded', () => {
  const amount = document.getElementById('settlementAmount');
  if (amount) {
    amount.addEventListener('input', () => {
      const max = Number(amount.max || 0);
      if (max && Number(amount.value) > max) amount.value = max;
      if (Number(amount.value) < 0) amount.value = 0;
    });
  }
});
