const yearSelect = document.getElementById('year');
const makeSelect = document.getElementById('make');
const modelSelect = document.getElementById('model');
const carSearchForm = document.getElementById('car-search');
const chosenVehicleInput = document.getElementById('chosen-vehicle');

// Function to populate year dropdown from JSON data
function populateYearDropdown(cars) {
  const years = [...new Set(cars.map(car => car.year))];
  years.forEach(year => {
    const option = document.createElement('option');
    option.value = year;
    option.innerText = year;
    yearSelect.appendChild(option);
  });
}

// Function to populate make dropdown based on selected year
function populateMakeDropdown(cars, selectedYear) {
  makeSelect.innerHTML = '<option value="">Select Make</option>'; // Clear previous options
  makeSelect.disabled = !selectedYear; // Enable dropdown only if year is selected

  if (selectedYear) {
    const makes = cars.filter(car => car.year === selectedYear).map(car => car.make);
    const uniqueMakes = [...new Set(makes)];
    uniqueMakes.forEach(make => {
      const option = document.createElement('option');
      option.value = make;
      option.innerText = make;
      makeSelect.appendChild(option);
    });
  }
}

// Function to populate model dropdown based on selected year and make
function populateModelDropdown(cars, selectedYear, selectedMake) {
  modelSelect.innerHTML = '<option value="">Select Model</option>'; // Clear previous options
  modelSelect.disabled = !selectedMake; // Enable dropdown only if make is selected

  if (selectedMake) {
    const models = cars.filter(car => car.year === selectedYear && car.make === selectedMake).map(car => car.model);
    models.forEach(model => {
      const option = document.createElement('option');
      option.value = model;
      option.innerText = model;
      modelSelect.appendChild(option);
    });
  }
}

// Load car data from JSON file
fetch('./assets/cars_parsed.json')
  .then(response => response.json())
  .then(cars => {
    populateYearDropdown(cars);

    yearSelect.addEventListener('change', () => {
      const selectedYear = parseInt(yearSelect.value, 10);
      populateMakeDropdown(cars, selectedYear);
      populateModelDropdown(cars, selectedYear, ''); // Reset model on year change
    });

    makeSelect.addEventListener('change', () => {
      const selectedYear = parseInt(yearSelect.value, 10);
      const selectedMake = makeSelect.value;
      populateModelDropdown(cars, selectedYear, selectedMake);
    });

    carSearchForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const year = document.getElementById('year').value.toLowerCase();
        const make = document.getElementById('make').value.toLowerCase();
        const model = document.getElementById('model').value.toLowerCase();
        chosenVehicleInput.value = `${year}-${make}-${model}`;
        const chosenVehicleUrl = `/posts/${chosenVehicleInput.value}`;  // Construct URL
        window.location.href = chosenVehicleUrl;  // Redirect using Javascript
      });
})